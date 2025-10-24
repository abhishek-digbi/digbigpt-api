# Ask Digbi Workflow

The Ask Digbi feature provides conversational answers to user questions. The workflow is orchestrated through several agents using LangFuse prompts.

1. **API Layer** – `POST /api/ask-digbi` receives the query and user context. The controller submits a background task via `process_ask_digbi_task`.
2. **Context Setup** – A `BaseModelContext` is built with conversation history, user information, and a query identifier. This context is passed to `AskDigbiAgent`.
3. **Intent Classification** – `AskDigbiAgent.ask` formats the conversation and invokes the intent classifier agent (`ASK_DIGBI_INTENT_CLASSIFIER_AGENT`). The response lists the actions to perform.
4. **Routing to Agents** – Each action is executed concurrently. Possible targets include the Nutrition, Personalization, Health Insights, and Support agents. The `_process_action` helper calls the relevant agent and collects responses.
5. **Summarization** – Once all actions complete, `summarize_response` uses the `ASK_DIGBI_SUMMARIZER_AGENT` prompt to craft the final message.
6. **Callback** – The final answer is sent back to Digbi via the configured callback URL.

LangFuse prompt keys (e.g., `Ask_Digbi_Intent_Classifier_Ops_Agent_Added`) are resolved through `AiCoreService` and `LangFuseService`. Variables required for each prompt are fetched by the `ToolService` before dispatching the request to the OpenAI adapter.
