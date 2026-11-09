#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/deploy/.provisioned.env"
KEY_PATH="${KEY_PATH:-$HOME/.ssh/jobify-ec2}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — run ./deploy/provision-ec2.sh first"
  exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

SSH=(ssh -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${EC2_USER}@${EC2_HOST}")

echo "==> Wait for SSH"
for i in $(seq 1 36); do
  if "${SSH[@]}" 'echo ok' >/dev/null 2>&1; then
    break
  fi
  sleep 5
  if [[ "$i" -eq 36 ]]; then
    echo "SSH not ready"
    exit 1
  fi
done

echo "==> Wait for docker + /opt/lernyra"
for i in $(seq 1 36); do
  if "${SSH[@]}" 'command -v docker >/dev/null && test -d /opt/lernyra/.git'; then
    break
  fi
  sleep 5
  if [[ "$i" -eq 36 ]]; then
    echo "Bootstrap not finished yet — check: ${SSH[*]} 'sudo journalctl -u cloud-final -n 50'"
    exit 1
  fi
done

echo "==> Write remote .env"
"${SSH[@]}" "cat > /opt/lernyra/.env" <<EOF
DOMAIN=${DOMAIN}
IMAGE=${IMAGE}
REMOTIVE_ENABLED=true
EOF
"${SSH[@]}" 'chmod 600 /opt/lernyra/.env'

echo "==> Pull & start"
"${SSH[@]}" 'cd /opt/lernyra && git fetch --depth 1 origin main && git reset --hard origin/main && docker compose -f docker-compose.prod.yml --env-file .env pull && docker compose -f docker-compose.prod.yml --env-file .env up -d'

echo "==> Health"
for i in $(seq 1 30); do
  if curl -fsS "https://${DOMAIN}/api/health" >/dev/null 2>&1; then
    curl -fsS "https://${DOMAIN}/api/health"; echo
    break
  fi
  sleep 5
  if [[ "$i" -eq 30 ]]; then
    echo "HTTPS not healthy yet — try: curl -v https://${DOMAIN}/api/health"
    "${SSH[@]}" 'cd /opt/lernyra && docker compose -f docker-compose.prod.yml --env-file .env ps'
  fi
done

if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  echo "==> GitHub Actions secrets"
  gh secret set EC2_HOST --repo lisss/lernyra --body "$EC2_HOST"
  gh secret set EC2_USER --repo lisss/lernyra --body "$EC2_USER"
  gh secret set EC2_SSH_KEY --repo lisss/lernyra < "$KEY_PATH"
  gh variable set DEPLOY_ENABLED --repo lisss/lernyra --body true
  echo "Deploy on push to main is enabled."
else
  echo "gh not authenticated — set secrets manually (see deploy/README.md)"
fi

echo ""
echo "Live: https://${DOMAIN}"
