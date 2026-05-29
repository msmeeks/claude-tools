# configs

Each `*.example.json` is a template for one backend. Copy it to `*.local.json`
and fill in your values:

```bash
cp ollama-lan.example.json ollama-lan.local.json
# edit ollama-lan.local.json — set LAN_IP_HERE to the Ollama host IP
```

`*.local.json` files are gitignored — they never leave your machine.

## Fields

- `api_base_url` — where claude-code-router forwards requests
- `api_key` — sent as Bearer token; leave `""` for local Ollama
- `models` — list what you have pulled; router picks from these
- `Router` — maps intents to `"provider,model"` strings:
  - `default` — most interactive tasks
  - `background` — cheap tasks (title generation, summarisation)
  - `think` — extended thinking / hard problems
  - `longContext` — tasks with large context windows

## Switching

`../claude-byom <profile>` swaps the active config atomically.
Running `../claude-byom ollama-lan` copies `ollama-lan.local.json` to
`~/.claude-code-router/config.json` then launches `ccr code`.
