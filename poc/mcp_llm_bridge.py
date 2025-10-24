#!/usr/bin/env python3
import os, json, argparse, asyncio, sys
from typing import Any, Tuple
from tabulate import tabulate
from openai import OpenAI

# MCP client imports (support both naming variants)
from mcp.client.session import ClientSession
try:
    from mcp.client.streamable_http import streamablehttp_client as http_client  # newer name
except ImportError:
    from mcp.client.streamable_http import streamable_http_client as http_client  # older name
try:
    from mcp.client.sse import sse_client
except Exception:
    sse_client = None  # optional

def prettify(payload: Any) -> str:
    if isinstance(payload, dict) and payload.get("columns") and payload.get("rows"):
        return tabulate(payload["rows"], headers=payload["columns"], tablefmt="github")
    return json.dumps(payload, indent=2, default=str)

async def mcp_call(tool: str, args: dict, url: str, transport: str):
    if transport == "http":
        ctx = http_client(url)
    elif transport == "sse":
        if not sse_client:
            raise RuntimeError("SSE client not available in this mcp version.")
        ctx = sse_client(url)
    else:
        raise ValueError("transport must be 'http' or 'sse'")

    async with ctx as (read, write, *rest):
        async with ClientSession(read, write) as s:
            await s.initialize()
            res = await s.call_tool(tool, args or {})
            # Extract JSON/text payload from MCP content parts
            for part in getattr(res, "content", []) or []:
                t = getattr(part, "type", "")
                if t == "json":
                    for key in ("json", "data", "value"):
                        if hasattr(part, key):
                            return getattr(part, key)
                if t == "text" and hasattr(part, "text"):
                    try:
                        return json.loads(part.text)
                    except Exception:
                        return {"text": part.text}
    return {}

def main():
    ap = argparse.ArgumentParser(description="Tiny LLM ⇄ MCP SQL agent")
    ap.add_argument("question", help="e.g., 'top 5 disease categories for Acme'")
    ap.add_argument("--mcp-url", default="http://127.0.0.1:8811/mcp/", help="MCP URL (/mcp/ for HTTP, /sse for SSE)")
    ap.add_argument("--transport", choices=["http","sse"], default="http", help="MCP transport")
    ap.add_argument("--model", default="gpt-4o-mini")
    args = ap.parse_args()

    # OpenAI client (uses OPENAI_API_KEY)
    client = OpenAI()

    tool_defs = [
        {"type":"function","function":{
            "name":"get_schema",
            "description":"Return columns/types for claims_demo.claims",
            "parameters":{"type":"object","properties":{},"additionalProperties":False}
        }},
        {"type":"function","function":{
            "name":"run_sql",
            "description":"Execute a read-only SELECT on claims_demo.claims and return rows/columns",
            "parameters":{"type":"object","properties":{
                "sql":{"type":"string","description":"SELECT only; no DML; reference claims_demo.claims"}
            },"required":["sql"],"additionalProperties":False}
        }},
    ]

    system = (
        "You are a Redshift SQL helper. "
        "First call get_schema to see allowed columns: employer_name, employee_name, disease_category, year_of_claim, claim_amount. "
        "Then create ONE safe SELECT (no DML) over claims_demo.claims and call run_sql. "
        "Aggregate when needed with GROUP BY. Return a concise final answer."
    )

    messages = [
        {"role":"system","content":system},
        {"role":"user","content":args.question},
    ]

    # ---- loop: assistant may call multiple tools (schema -> sql) ----
    # ALWAYS include 'tools' when using 'tool_choice'.
    
    # That snippet is the first handshake with the model for tool use.
    # It sends a chat request with:
    #    messages: your system + user prompt so the model knows the task.
    #    tools=tool_defs: the two functions it’s allowed to call (get_schema, run_sql) and their JSON schemas.
    #    tool_choice="auto": tells the model it may call one or more tools with arguments if needed.
    # resp = client.chat.completions.create(...) runs that request.
    # assistant = resp.choices[0].message grabs the model’s reply, which will be either:
    #    Plain text (no tools needed), or
    #    One or more tool_calls (e.g., first call get_schema, then later run_sql).
    # After this, your loop checks assistant.tool_calls; if present, 
    # you execute those tools, append their results, and ask the model again. 
    
    print(f"Calling OpenAPI with Messages: {messages}")
    resp = client.chat.completions.create(
        model=args.model, messages=messages, tools=tool_defs, tool_choice="auto"
    )
    assistant = resp.choices[0].message
    print(f"OpenAPI Response : {assistant.tool_calls} \n\n")

    # Keep asking until no tool_calls remain (max 3 rounds)
    for _ in range(5):
        if not assistant.tool_calls:
            break

        # Add the assistant message that contains tool_calls
        messages.append({
            "role": "assistant",
            "content": assistant.content or "",
            "tool_calls": [tc.model_dump() for tc in assistant.tool_calls],
        })

        # Execute each tool via MCP and append tool results
        for tc in assistant.tool_calls:
            name = tc.function.name
            fargs = json.loads(tc.function.arguments or "{}")
            if name == "get_schema":
                result = asyncio.run(mcp_call("get_schema", {}, args.mcp_url, args.transport))
            elif name == "run_sql":
                result = asyncio.run(mcp_call("run_sql", {"sql": fargs["sql"]}, args.mcp_url, args.transport))
            else:
                result = {"error": f"unknown tool {name}"}

            # attach a pre-rendered table if rows/cols present
            if isinstance(result, dict) and result.get("columns") and result.get("rows"):
                result["table"] = prettify(result)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

        # Ask model again; allow another tool or a final answer
        print(f"Calling OpenAPI with Messages: {messages}")
        resp = client.chat.completions.create(
            model=args.model, messages=messages, tools=tool_defs, tool_choice="auto"
        )
        assistant = resp.choices[0].message
        print(f"OpenAPI Response: {assistant.tool_calls} \n\n")

    # If still no natural-language content, force a final answer with tool use disabled
    print(f"Calling for Summary from OpenAPI with Messages: {messages}")
    if not assistant.content:
        resp = client.chat.completions.create(
            model=args.model, messages=messages, tools=tool_defs, tool_choice="none"
        )
        assistant = resp.choices[0].message

    print("\n\n RESULTS: ----------------------------------------------------\n\n")
    # print(assistant.content or "(no content) \n\n")

    # If the last tool produced a 'table', print it (nice CLI output)
    for m in reversed(messages):
        if m.get("role") == "tool":
            try:
                payload = json.loads(m["content"])
                if isinstance(payload, dict) and payload.get("table"):
                    print("\n" + payload["table"])
            except Exception:
                pass
            break

if __name__ == "__main__":
    # Quick sanity: advise correct URL per transport
    # HTTP transport requires /mcp/; SSE requires /sse
    sys.exit(main())
