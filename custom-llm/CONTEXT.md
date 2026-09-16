# custom-llm

Points Claude Code at non-Anthropic backends without modifying Claude Code. `claude-lan.sh`
launches `claude-code-router` as a local proxy and exports
`ANTHROPIC_BASE_URL=http://127.0.0.1:3456`, so the CLI only ever talks to localhost while the
proxy translates the Anthropic Messages API into the backend's own format.

Backends, model mapping, and setup:
[../docs/features/custom-llm.md](../docs/features/custom-llm.md).

## Language

**Router**:
The `claude-code-router` proxy process. Owns backend selection and request translation.
_Avoid_: gateway, shim, bridge

**Backend**:
The LLM actually serving the request — Ollama on the LAN, Ollama on a cloud VM, Gemini, or
OpenAI.
_Avoid_: provider, endpoint, model (a backend serves several models)

## Boundaries

- Nothing here changes Claude Code itself; the only lever is `ANTHROPIC_BASE_URL`.
- Router config carries backend API keys. It stays out of this repo — never commit a
  populated router config.
- Capability is not equivalent across backends. Tool use and long-context behaviour differ,
  so a skill that works on Claude may not work behind the router.
