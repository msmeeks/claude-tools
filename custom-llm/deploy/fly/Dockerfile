FROM ollama/ollama:latest

# Install Caddy
RUN apt-get update && apt-get install -y --no-install-recommends \
    debian-keyring debian-archive-keyring apt-transport-https curl \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
       | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
       | tee /etc/apt/sources.list.d/caddy-stable.list \
    && apt-get update && apt-get install -y caddy \
    && rm -rf /var/lib/apt/lists/*

# Add a non-root user. Ollama and Caddy both work on ports > 1024 as non-root.
RUN addgroup --system ollama-caddy && \
    adduser --system --ingroup ollama-caddy ollama-caddy

COPY Caddyfile.example /etc/caddy/Caddyfile
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && \
    chown -R ollama-caddy:ollama-caddy /etc/caddy /root/.ollama 2>/dev/null || true

# Caddy HTTPS (443) and Ollama API (11434, internal only)
EXPOSE 443

USER ollama-caddy
ENTRYPOINT ["/entrypoint.sh"]
