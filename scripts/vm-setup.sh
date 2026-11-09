#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-https://github.com/lisss/lernyra.git}"
APP_DIR="${HOME}/lernyra"
PORT="${PORT:-8000}"

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y git ca-certificates curl
  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER" || true
  fi
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf -y install git curl
  if ! command -v docker >/dev/null 2>&1; then
    sudo dnf -y install docker
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER" || true
  fi
else
  echo "Unsupported distro: install git + docker manually, then re-run."
  exit 1
fi

# Open host firewall if present (OCI often needs BOTH iptables and Security List)
if command -v iptables >/dev/null 2>&1; then
  sudo iptables -I INPUT -p tcp --dport "${PORT}" -j ACCEPT || true
  sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT || true
  if command -v netfilter-persistent >/dev/null 2>&1; then
    sudo netfilter-persistent save || true
  elif [[ -f /etc/iptables/rules.v4 ]]; then
    sudo sh -c 'iptables-save > /etc/iptables/rules.v4' || true
  fi
fi

mkdir -p "$(dirname "$APP_DIR")"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
# Prefer docker group; fall back to sudo if fresh session without re-login
DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
fi

"${DOCKER[@]}" build -t lernyra:latest .
"${DOCKER[@]}" rm -f lernyra 2>/dev/null || true
"${DOCKER[@]}" run -d --name lernyra --restart unless-stopped \
  -p "${PORT}:8000" \
  -e API_CORS_ORIGINS='*' \
  -e DATABASE_URL='sqlite:////tmp/lernyra.db' \
  lernyra:latest

echo
echo "App should be at: http://$(curl -s --max-time 3 ifconfig.me 2>/dev/null || echo YOUR_PUBLIC_IP):${PORT}/"
echo "Health: curl http://127.0.0.1:${PORT}/api/health"
