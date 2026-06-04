# custom-llm

Route the `claude` CLI to non-Anthropic LLM backends: Ollama on a LAN laptop,
Ollama on a private cloud VM, Google Gemini, or OpenAI — without modifying
Claude Code itself. A local proxy ([claude-code-router]) translates the
Anthropic Messages API to whichever backend you choose.

[claude-code-router]: https://github.com/musistudio/claude-code-router

## Contents

```
custom-llm/
  README.md
  install.sh              # install ccr, scaffold ~/.claude-code-router/
  claude-byom             # launcher: ./claude-byom <profile>
  verify.sh               # smoke-test the active proxy + backend
  configs/
    ollama-lan.example.json     # Ollama on LAN laptop
    ollama-cloud.example.json   # Ollama on remote VM (Tailscale/SSH/Caddy)
    gemini.example.json         # Google Gemini
    openai.example.json         # OpenAI
    README.md
  network/
    tailscale-setup.md    # zero-config VPN (recommended)
    ssh-tunnel.sh         # port-forward via SSH
    caddy/
      Caddyfile.example   # HTTPS + basicauth reverse proxy
      deploy-notes.md
  deploy/
    fly/                  # fly.io recipe (Dockerfile, fly.toml, entrypoint)
    aws/                  # EC2 recipe (user-data script + sizing guide)
```

## Prerequisites

- `claude` CLI installed and working against Anthropic
- Node 18+ and `npm` (for claude-code-router)
- For Ollama backends: Ollama installed on the host serving the model
- For Gemini: a Google AI Studio API key
- For OpenAI: an OpenAI API key
- For remote Ollama: Tailscale, SSH access, or a domain name (see Networking)

## Quick start

```bash
# 1. Install claude-code-router
bash install.sh

# 2. Copy a config template and fill in your values
cp configs/ollama-lan.example.json configs/ollama-lan.local.json
$EDITOR configs/ollama-lan.local.json   # set LAN_IP_HERE

# 3. Launch
./claude-byom ollama-lan
```

Claude Code opens and all LLM calls go to your Ollama instance.
Switch profiles at any time by re-running `./claude-byom <profile>`.

## Backends

### Ollama on a LAN laptop

Start Ollama on the other laptop, binding to its LAN IP so this machine can
reach it. Only do this on a trusted private network — not public Wi-Fi.

```bash
# On the Ollama host
OLLAMA_HOST=0.0.0.0:11434 ollama serve
ollama pull qwen2.5-coder:32b
```

Then set `LAN_IP_HERE` in `configs/ollama-lan.local.json` to the host's
local IP (e.g. `192.168.1.42`). The `api_base_url` becomes
`http://192.168.1.42:11434/v1/chat/completions`.

```bash
./claude-byom ollama-lan
```

### Ollama on a cloud VM (fly.io or AWS)

Deploy the Ollama + Caddy container — see `deploy/fly/` (fly.io) or
`deploy/aws/` (EC2). Caddy provides HTTPS and basic auth so the endpoint
is safe to expose publicly.

Once deployed, set `configs/ollama-cloud.local.json`:

```json
{
  "Providers": [{
    "name":        "ollama",
    "api_base_url": "https://your-domain.example.com/v1/chat/completions",
    "api_key":     "<base64(ollama:YOUR_PASSWORD)>"
  }]
}
```

```bash
./claude-byom ollama-cloud
```

### Gemini

Get a key from [Google AI Studio](https://aistudio.google.com/apikey), then:

```bash
cp configs/gemini.example.json configs/gemini.local.json
# Replace YOUR_GEMINI_API_KEY
./claude-byom gemini
```

Note: prompts are sent to Google's servers under
[Gemini API terms](https://ai.google.dev/gemini-api/terms). Do not paste
secrets or confidential code when this backend is active.

### OpenAI

```bash
cp configs/openai.example.json configs/openai.local.json
# Replace YOUR_OPENAI_API_KEY
./claude-byom openai
```

Note: prompts are sent to OpenAI's servers under
[OpenAI's API usage policy](https://openai.com/policies/api-data-usage-policies).
Do not paste secrets or confidential code when this backend is active.

## Networking for remote Ollama

Three options — pick the one that fits your setup:

### Tailscale (recommended)

Zero public exposure, no cert setup, works for both LAN laptops and cloud VMs.
See `network/tailscale-setup.md`.

### SSH tunnel

No new infra. Forward port 11434 from the remote to localhost, then use
`http://127.0.0.1:11434/v1/chat/completions` as the `api_base_url`.

```bash
REMOTE_HOST=my-vm.example.com bash network/ssh-tunnel.sh
```

Keep the terminal open while Claude Code is running. See the script for
`REMOTE_USER`, `LOCAL_PORT`, and `SSH_KEY` env overrides.

### Caddy reverse proxy with TLS

Public HTTPS URL with basicauth. Required for the fly.io/EC2 deployments.
See `network/caddy/deploy-notes.md`.

## Verifying

With `./claude-byom <profile>` running in one terminal, open a second terminal:

```bash
./verify.sh
```

Expected output: proxy up, active provider and model printed, canary prompt
returns `BACKEND_OK`. If the proxy is down, `verify.sh` will say so with a
fix hint.

## Switching backends

```bash
./claude-byom ollama-lan    # LAN Ollama
./claude-byom gemini        # Gemini
./claude-byom openai        # OpenAI
```

Each call atomically replaces `~/.claude-code-router/config.json` and launches
a fresh `ccr code` session. Previous profiles are untouched in `configs/`.

## Troubleshooting

**Port 3456 in use**: another `ccr` process is already running.
`lsof -i :3456` to find it; `kill <PID>` then retry.

**ccr cannot reach Ollama**: check `api_base_url` in the active config, confirm
Ollama is running (`ollama list`), and confirm the port/IP is reachable
(`curl http://<host>:11434/api/tags`).

**Model not found**: the model name in `configs/*.local.json` must exactly match
a pulled model. Run `ollama list` on the host to see available names.

**401 from Gemini or OpenAI**: the `api_key` value in your `.local.json` is
wrong or expired. Regenerate it in the provider's console.

**TLS handshake failure behind Caddy**: Let's Encrypt needs a valid DNS A record
pointing at your server. Check DNS propagation with `dig +short your-domain.com`
and ensure port 443 is open in your security group / firewall.

**`ccr: command not found`**: run `bash install.sh` to install it.

## Security notes

- Never bind Ollama to `0.0.0.0:11434` on a public IP without Caddy
  basic-auth + TLS in front of it.
- `*.local.json` files are gitignored — run `git status` before committing to
  confirm no secrets are staged.
- API keys (Gemini, OpenAI) belong in `*.local.json` files, not in
  `*.example.json` or committed anywhere else.
- `claude-code-router` listens on `127.0.0.1:3456` by default. Do not expose
  that port to other hosts.
- For the Caddy setup: the basicauth password hash goes in the Caddyfile; the
  plaintext password goes in a fly secret / AWS SSM parameter. Rotate it
  periodically.
- SSH tunnels: prefer key-based auth and disable password auth on the remote sshd.
- Re-audit `@musistudio/claude-code-router` with `npm audit` after each version
  upgrade — all LLM traffic flows through it.
- Prompts sent to Gemini or OpenAI are processed under those providers' data
  retention policies. Avoid sending confidential code or secrets to cloud backends.
