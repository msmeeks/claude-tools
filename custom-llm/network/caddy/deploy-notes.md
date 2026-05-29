# Networking: Caddy reverse proxy with TLS

Use when you want a stable public HTTPS URL for your remote Ollama instance
(fly.io, EC2, or any VM with a domain name). Caddy handles Let's Encrypt
certificate issuance automatically.

## Generate a password hash

```bash
caddy hash-password --plaintext YOUR_STRONG_PASSWORD
# outputs: $2a$14$...
```

Store this hash — not the plaintext password — in the Caddyfile.
Store the plaintext password in a password manager or fly/AWS secret.

## fly.io deployment

Set the hash as a fly secret (never in fly.toml):

```bash
fly secrets set CADDY_BASIC_AUTH_HASH='$2a$14$...'
```

The Caddyfile reads it via `{env.CADDY_BASIC_AUTH_HASH}` (see example).

You must also set a DNS A record pointing your domain to the fly.io IP:

```bash
fly ips list          # get your allocated IP
# add DNS A record: REPLACE_YOUR_DOMAIN.example.com → <fly IP>
```

## EC2 deployment

Set the hash as an environment variable before starting Caddy:

```bash
# Store in /etc/caddy/caddy.env (chmod 600, owned by caddy user)
CADDY_BASIC_AUTH_HASH='$2a$14$...'

# Reference in systemd unit:
# EnvironmentFile=/etc/caddy/caddy.env

systemctl reload caddy
```

Or store in AWS SSM Parameter Store and inject at boot via user-data.

## Client configuration

Once the domain resolves and TLS is working, update `ollama-cloud.local.json`:

```json
{
  "Providers": [{
    "name": "ollama",
    "api_base_url": "https://REPLACE_YOUR_DOMAIN.example.com/v1",
    "api_key": "BASIC_AUTH_TOKEN_HERE"
  }]
}
```

The `api_key` field is sent as `Authorization: Bearer <token>` by
claude-code-router. For Caddy basicauth the token must be
`base64(username:password)`. Construct it:

```bash
echo -n "ollama:YOUR_STRONG_PASSWORD" | base64
```

Paste the output as the `api_key` value.

## Verify TLS is working

```bash
curl --fail --ssl-reqd https://REPLACE_YOUR_DOMAIN.example.com/api/tags \
  -u ollama:YOUR_STRONG_PASSWORD
```

If the cert is invalid or expired, `--ssl-reqd` will error rather than
silently connecting insecurely.

## Pros and cons

- **Pros**: stable public URL, standard HTTPS, no VPN client required
- **Cons**: requires a domain name, DNS propagation delay on first deploy,
  Caddy must be kept up-to-date to renew certs
