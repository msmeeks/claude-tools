# custom-llm

## Summary
Routes Claude Code to non-Anthropic LLM backends (Ollama on a LAN, Ollama on a cloud VM, Google Gemini, OpenAI) without modifying Claude Code itself. A local proxy (`claude-code-router`) translates the Anthropic Messages API into backend-specific format; Claude Code only ever sees `ANTHROPIC_BASE_URL=http://127.0.0.1:3456`.

## Users / Use Cases
- **Developer (local)**: point Claude Code at a local Ollama instance to keep prompts off Anthropic servers or reduce API cost
- **Developer (remote)**: run a GPU-backed Ollama VM and share it across machines via Tailscale, SSH tunnel, or Caddy+TLS
- **Developer (cloud APIs)**: use Gemini or OpenAI as drop-in Claude backends

## Technologies
- [claude-code-router](https://github.com/musistudio/claude-code-router) — proxy that translates Anthropic Messages API to backend-specific formats; all LLM traffic flows through it
- Ollama — local/self-hosted model runner
- Tailscale / SSH / Caddy — networking layer for reaching remote Ollama instances
- fly.io / AWS EC2 — cloud deployment targets for Ollama + Caddy

## Technical Overview
`install.sh` installs `claude-code-router` (ccr) and scaffolds `~/.claude-code-router/`. The launcher `claude-byom <profile>` copies `configs/<profile>.local.json` to `~/.claude-code-router/config.json` and starts a fresh `ccr code` session, which sets `ANTHROPIC_BASE_URL=http://127.0.0.1:3456` for the Claude Code process. Every LLM call from Claude Code hits ccr, which rewrites it to the configured backend's API format and returns an Anthropic-shaped response. `verify.sh` smoke-tests the active proxy and backend end-to-end.

## API Endpoints
N/A — this is a local proxy tool, not a web service.

## Key Files
| File | Purpose |
|---|---|
| `custom-llm/install.sh` | Install ccr, scaffold config directory |
| `custom-llm/claude-byom` | Launcher: activate a named profile and start ccr |
| `custom-llm/verify.sh` | Smoke-test the active proxy and backend |
| `custom-llm/configs/*.example.json` | Template configs for each backend |
| `custom-llm/network/tailscale-setup.md` | Tailscale VPN setup guide (recommended) |
| `custom-llm/network/ssh-tunnel.sh` | SSH port-forward to a remote Ollama host |
| `custom-llm/network/caddy/Caddyfile.example` | Caddy HTTPS + basicauth reverse proxy |
| `custom-llm/deploy/fly/` | fly.io recipe: Dockerfile, entrypoint, fly.toml |
| `custom-llm/deploy/aws/` | AWS EC2 recipe: user-data script + sizing guide |

## Technical Detail

### Config structure
Each `configs/<profile>.local.json` (gitignored) follows the ccr schema:

```json
{
  "Providers": [{ "name": "...", "api_base_url": "...", "api_key": "...", "models": [...] }],
  "Router": { "default": "provider,model", "background": "...", "think": "...", "longContext": "..." }
}
```

Copy an `*.example.json`, fill in real values, and save as `*.local.json`. See `configs/README.md`.

### Networking options for remote Ollama
- **Tailscale** (recommended): zero public exposure, no cert setup — see `network/tailscale-setup.md`
- **SSH tunnel**: `REMOTE_HOST=my-vm bash network/ssh-tunnel.sh` — forwards port 11434 to localhost
- **Caddy + TLS**: public HTTPS with basicauth, required for fly.io/EC2 deployments — see `network/caddy/deploy-notes.md`

### Cloud deployment
- `deploy/fly/` — Dockerfile + `fly.toml.example`; Caddy basicauth password hash sourced from a fly secret
- `deploy/aws/` — `ec2-user-data.sh.example` bootstraps Ollama + Caddy on launch; password from AWS SSM

### Security
- `*.local.json` files are gitignored; confirm with `git status` before committing
- `chmod 600` is enforced on config files by `install.sh`
- ccr binds to `127.0.0.1:3456` only — never expose this port externally
- Caddy basicauth hash is stored in the Caddyfile; plaintext goes in a fly secret / SSM parameter only
- Gemini and OpenAI prompts leave your machine under those providers' data retention policies — avoid sending confidential code or secrets
- Re-audit `@musistudio/claude-code-router` with `npm audit` after each version upgrade

## Changelog
| Date | Change |
|---|---|
| 2026-05-29 | Initial documentation |
