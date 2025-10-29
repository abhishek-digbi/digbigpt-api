# Project Overview

This repository contains the **Digbi AI Agent Service**, a FastAPI application that orchestrates multiple LLM-based agents to provide health and nutrition related features. The service exposes REST endpoints, manages LangFuse prompts, and coordinates several specialized agents such as the Ask Digbi conversational agent and the Meal Rating workflow.

## Folder Structure

- `agent_core/` – Core services and utilities for running agents and interacting with LangFuse and OpenAI.
- `tools/` – Tool registry and data aggregation layer.
- `orchestrator/` – Application layer with API controllers and specialized agent orchestrators.
- `app/` – Application factory and startup logic.
- `utils/` – Helper utilities for database and logging.
- `tests/` – Unit tests for the API and workflows.

See `README.md` for installation and setup instructions.
