#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/lisss/lernyra.git}"
APP_DIR="${APP_DIR:-/opt/lernyra}"
APP_USER="${APP_USER:-ubuntu}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl git

if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

usermod -aG docker "$APP_USER" || true

mkdir -p "$APP_DIR"
if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone --depth 1 "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch --depth 1 origin main
  git -C "$APP_DIR" reset --hard origin/main
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/deploy/.env.example" "$APP_DIR/.env"
  chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo ""
  echo "Created $APP_DIR/.env — edit DOMAIN / DUCKDNS_* before starting:"
  echo "  nano $APP_DIR/.env"
  echo "Then:"
  echo "  cd $APP_DIR && docker compose -f docker-compose.prod.yml --env-file .env up -d"
else
  echo "Existing $APP_DIR/.env kept."
fi

echo "Bootstrap complete."
