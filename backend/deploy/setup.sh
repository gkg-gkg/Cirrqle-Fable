#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Cirqle backend — one-shot setup for a fresh Amazon Linux 2023 EC2 instance.
#
# Run it ON THE SERVER (logged in as ec2-user) with a single command:
#   curl -fsSL https://raw.githubusercontent.com/gkg-gkg/Cirrqle-Fable/main/backend/deploy/setup.sh | bash
#
# It is safe to run again later to deploy updates — it pulls the latest code,
# reinstalls dependencies, and restarts the service, WITHOUT touching your
# .env or your existing database (so users are preserved).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="https://github.com/gkg-gkg/Cirrqle-Fable.git"
APP_DIR="$HOME/cirqle"
BACKEND_DIR="$APP_DIR/backend"

echo "== 1/6 Installing system packages (python, pip, git) =="
sudo dnf install -y python3 python3-pip git

echo "== 2/6 Fetching the code from GitHub =="
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull
else
  git clone "$REPO_URL" "$APP_DIR"
fi

echo "== 3/6 Creating the Python virtual environment + installing dependencies =="
python3 -m venv "$BACKEND_DIR/.venv"
"$BACKEND_DIR/.venv/bin/pip" install --upgrade pip
"$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

echo "== 4/6 Creating .env (only if it does not exist yet) =="
if [ ! -f "$BACKEND_DIR/.env" ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > "$BACKEND_DIR/.env" <<EOF
CIRQLE_SECRET_KEY=$SECRET
CIRQLE_DB_PATH=$BACKEND_DIR/cirqle.db
CIRQLE_CORS_ORIGINS=*
EOF
  echo "   .env created with a fresh random secret key."
else
  echo "   .env already exists — keeping it (and your users) untouched."
fi

echo "== 5/6 Installing + starting the systemd service =="
sudo cp "$BACKEND_DIR/deploy/cirqle-api.service" /etc/systemd/system/cirqle-api.service
sudo systemctl daemon-reload
sudo systemctl enable cirqle-api
sudo systemctl restart cirqle-api

echo "== 6/6 Done. Current service status: =="
sleep 2
sudo systemctl --no-pager status cirqle-api | head -n 12
echo ""
echo "✅ The API is now listening on port 8000."
echo "   Test it from your laptop:  curl http://<YOUR_SERVER_PUBLIC_IP>:8000/"
