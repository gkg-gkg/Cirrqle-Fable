#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Add HTTPS to the Cirqle backend using Caddy (which auto-fetches a free
# Let's Encrypt certificate and renews it forever). Caddy listens on 443/80 and
# forwards requests to the FastAPI app on 127.0.0.1:8000.
#
# Run on the server, passing your domain:
#   curl -fsSL https://raw.githubusercontent.com/gkg-gkg/Cirrqle-Fable/main/backend/deploy/setup_https.sh | bash -s cirqle.duckdns.org
#
# Requirements: ports 80 and 443 open to the world (they already are), and the
# domain's DNS pointing at THIS server's public IP.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  echo "ERROR: pass your domain, e.g.  ... | bash -s cirqle.duckdns.org" >&2
  exit 1
fi

echo "== 1/4 Downloading the Caddy web server =="
if ! command -v caddy >/dev/null 2>&1; then
  ARCH=$(uname -m); case "$ARCH" in x86_64) A=amd64;; aarch64) A=arm64;; *) A=amd64;; esac
  sudo curl -fsSL "https://caddyserver.com/api/download?os=linux&arch=$A" -o /usr/bin/caddy
  sudo chmod +x /usr/bin/caddy
fi
caddy version

echo "== 2/4 Writing the Caddy config for $DOMAIN =="
sudo mkdir -p /etc/caddy
sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
$DOMAIN {
    reverse_proxy 127.0.0.1:8000
}
EOF

echo "== 3/4 Installing + starting the Caddy service =="
sudo tee /etc/systemd/system/caddy.service >/dev/null <<'EOF'
[Unit]
Description=Caddy (HTTPS reverse proxy for Cirqle)
After=network.target

[Service]
ExecStart=/usr/bin/caddy run --config /etc/caddy/Caddyfile
ExecReload=/usr/bin/caddy reload --config /etc/caddy/Caddyfile
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable caddy
sudo systemctl restart caddy

echo "== 4/4 Done — Caddy is fetching your certificate (can take ~30-60s) =="
sleep 5
sudo systemctl --no-pager status caddy | head -n 10
echo ""
echo "✅ Once the cert is issued, your API is live at:  https://$DOMAIN/"
echo "   Test:  curl https://$DOMAIN/"
