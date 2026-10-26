# ARYA — AI Study Companion

ARYA is a three-person learning project for building an AI-supported study companion while practicing Git and GitHub collaboration.

> **Starter state:** this repository currently contains a visual React mockup and an empty backend folder layout. The light/dark theme, mobile navigation, and new-chat notice work locally; chat, AI, database, document ingestion, retrieval, memory, and MCP features are not implemented.

## Run the UI mockup

Requirements: Node.js 20+ and npm.

```powershell
cd frontend
npm install
npm run dev
```

Use the local URL printed by Vite. The UI is a static starting point for frontend work; sending messages and backend navigation are not connected.

## Project design

- [High-level design](docs/high-level-design.md) — system context, components, data flows, and phased delivery.
- [Architecture and team guide](docs/architecture.md) — folder ownership, API/module contracts, testing, safety, and implementation rules.

## Suggested three-person ownership

| Teammate | Initial ownership | Main areas |
|---|---|---|
| Person 1 | UI and document knowledge | `frontend/`, `backend/app/rag/` |
| Person 2 | Database and persistent memory | `backend/app/db/`, `backend/app/memory/` |
| Person 3 | MCP and agent orchestration | `backend/app/mcp/`, `backend/app/agent/` |

All three review interface changes, tests, and integration pull requests. Keep work on feature branches; do not commit directly to `main`.

## Local files and secrets

The `.env`, local virtual environment, Chroma database, study notes, and generated output are local development material and are excluded from Git. They have been left untouched. Never force-add secrets, private notes, generated databases, or environment folders.
