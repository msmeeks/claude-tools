# Deploy Ollama on fly.io

Runs Ollama + Caddy in a single container. Caddy provides HTTPS with automatic
Let's Encrypt certs and basic-auth in front of the Ollama API.

## Prerequisites

- `fly` CLI installed: `brew install flyctl`
- Fly.io account and logged in: `fly auth login`
- A domain name you control (for HTTPS and basicauth)

## Deploy

```bash
cd custom-llm/deploy/fly

# 1. Create the app (do not deploy yet)
fly launch --no-deploy --name REPLACE_YOUR_APP_NAME

# 2. Create a persistent volume for models (50 GB; resize as needed)
fly volumes create ollama_models --size 50 --region ord

# 3. Copy and customise fly.toml
cp fly.toml.example fly.toml
# edit fly.toml: set app name and region

# 4. Copy and customise the Caddyfile
cp ../../network/caddy/Caddyfile.example Caddyfile
# edit Caddyfile: replace REPLACE_YOUR_DOMAIN.example.com

# 5. Generate a password hash and set it as a secret
caddy hash-password --plaintext YOUR_STRONG_PASSWORD
fly secrets set CADDY_BASIC_AUTH_HASH='$2a$14$HASH_OUTPUT_HERE'

# 6. Deploy
fly deploy

# 7. Point your DNS A record at your fly.io IP
fly ips list
# Add A record: your-domain.com → <fly IP>

# 8. Pull a model (wait for deploy to complete first)
fly ssh console -C "ollama pull qwen2.5-coder:7b"
```

## Configure the client

Update `configs/ollama-cloud.local.json`:

```json
{
  "Providers": [{
    "name": "ollama",
    "api_base_url": "https://YOUR_DOMAIN.example.com/v1",
    "api_key": "<base64(ollama:YOUR_STRONG_PASSWORD)>"
  }]
}
```

Construct the api_key:
```bash
echo -n "ollama:YOUR_STRONG_PASSWORD" | base64
```

Then launch:
```bash
./claude-byom ollama-cloud
```

## Sizing notes

| Model | RAM needed | fly.io VM |
|---|---|---|
| llama3.1:8b | ~6 GB | `performance-2x` (4 GB) + offloading |
| qwen2.5-coder:7b | ~5 GB | `performance-2x` |
| qwen2.5-coder:32b | ~20 GB + GPU | `a10g` GPU instance |

GPU instances cost more. For CPU-only inference, `performance-4x` (8 GB) handles
most 7B models reasonably. Run `fly scale vm performance-4x` to resize.

## Secrets

- `CADDY_BASIC_AUTH_HASH` — set via `fly secrets set`, never in fly.toml
- Never put `api_key` or passwords in the `[env]` block of fly.toml
