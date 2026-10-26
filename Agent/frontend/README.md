# ARYA frontend

This React + Vite app is a **UI mockup**. The theme switch persists light/dark preference, the mobile menu opens and closes, and “New study chat” displays a notice explaining that chat is not connected. Chat sending, prompt suggestions, and unimplemented sections are intentionally disabled. No chat state, API service, or backend connection is included yet.

Its source is organized by responsibility:

```text
src/
  components/
    layout/       App shell, sidebar, brand, top bar
    theme/        Theme preference hook
    ui/           Shared visual primitives such as icons
  features/
    chat/         Chat page, disabled composer, and welcome panel
  App.jsx         Feature composition
  main.jsx        React entry point
  index.css       Global styles and design tokens
```

## Run locally

```powershell
npm install
npm run dev
```

When the backend contract is agreed, implement a feature API client and state hook in `src/features/chat/`, then enable chat controls as each behavior is implemented and tested. See `../docs/architecture.md`.
