# Networking: Tailscale

Best option for LAN laptop or private cloud VM. No public IP exposure, no
cert management, works identically for both use cases.

## Setup

### On the Ollama host (laptop or cloud VM)

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Bind Ollama to the Tailscale interface only.
# IMPORTANT: only use 0.0.0.0 here if Tailscale is the ONLY network interface
# (e.g., a fly.io private network VM). On a laptop, prefer the tailnet IP.
export OLLAMA_HOST=0.0.0.0:11434
ollama serve
```

To find your Tailscale IP:
```bash
tailscale ip -4
# e.g. 100.64.0.5
```

### On the client (the laptop running claude)

```bash
# Install Tailscale (macOS)
brew install --cask tailscale
# Then: open Tailscale.app and sign in to the same tailnet

# Verify connectivity
curl http://100.64.0.5:11434/api/tags
```

## Configure the backend

Edit `configs/ollama-cloud.local.json` (copy from example first):

```json
{
  "Providers": [{
    "name": "ollama",
    "api_base_url": "http://100.64.0.5:11434/v1",
    "api_key": ""
  }]
}
```

Or use the MagicDNS hostname if Tailscale MagicDNS is enabled:

```json
"api_base_url": "http://my-ollama-host.tail1234.ts.net:11434/v1"
```

## Tailscale ACLs (optional but recommended)

In the Tailscale admin console, lock down the Ollama node so only your
client machine can reach port 11434:

```json
{
  "acls": [
    {
      "action": "accept",
      "src":    ["tag:client"],
      "dst":    ["tag:ollama-host:11434"]
    }
  ]
}
```

## Pros and cons

- **Pros**: zero public exposure, no TLS setup, works across NAT, free tier
  covers personal use
- **Cons**: both ends must have Tailscale running; requires a Tailscale account
