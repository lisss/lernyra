#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/deploy/.provisioned.env"
KEY_PATH="${KEY_PATH:-$HOME/.ssh/jobify-ec2}"

: "${DUCKDNS_SUBDOMAIN:?set DUCKDNS_SUBDOMAIN (e.g. lernyra)}"
: "${DUCKDNS_TOKEN:?set DUCKDNS_TOKEN}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

DOMAIN="${DUCKDNS_SUBDOMAIN}.duckdns.org"
SSH=(ssh -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new "${EC2_USER}@${EC2_HOST}")

echo "==> Update DuckDNS → ${EC2_HOST}"
curl -fsS "https://www.duckdns.org/update?domains=${DUCKDNS_SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=${EC2_HOST}"
echo

APP_DIR="${APP_DIR:-/opt/lernyra}"
IMAGE_REF="${IMAGE:-ghcr.io/lisss/lernyra:latest}"

echo "==> Ensure app dir ${APP_DIR} (migrate older dirs if needed)"
"${SSH[@]}" "set -e
for old in /opt/pathquire /opt/casty /opt/cast /opt/jobify; do
  if [ -d \"\$old\" ] && [ ! -e '${APP_DIR}' ]; then
    sudo mv \"\$old\" '${APP_DIR}'
  fi
done
mkdir -p '${APP_DIR}'
"

echo "==> Rewrite remote .env DOMAIN=${DOMAIN} (dir ${APP_DIR})"
"${SSH[@]}" "cat > '${APP_DIR}/.env'" <<EOF
DOMAIN=${DOMAIN}
DUCKDNS_SUBDOMAIN=${DUCKDNS_SUBDOMAIN}
DUCKDNS_TOKEN=${DUCKDNS_TOKEN}
PUBLIC_SITE_URL=https://${DOMAIN}
IMAGE=${IMAGE_REF}
REMOTIVE_ENABLED=true
EOF
"${SSH[@]}" "chmod 600 '${APP_DIR}/.env'"

echo "==> Restart with duckdns profile"
"${SSH[@]}" "cd '${APP_DIR}' &&
  (git remote set-url origin https://github.com/lisss/lernyra.git 2>/dev/null || true) &&
  git fetch --depth 1 origin main &&
  git reset --hard origin/main &&
  docker image prune -af || true
  if ! docker compose -f docker-compose.prod.yml --profile duckdns --env-file .env pull; then
    for fallback in ghcr.io/lisss/pathquire:latest ghcr.io/lisss/cast:latest; do
      if docker pull \"\$fallback\"; then
        sed -i \"s|^IMAGE=.*|IMAGE=\${fallback}|\" .env
        break
      fi
    done
    docker compose -f docker-compose.prod.yml --profile duckdns --env-file .env pull
  fi &&
  docker rm -f lernyra-caddy lernyra-api lernyra-duckdns pathquire-caddy pathquire-api pathquire-duckdns cast-caddy cast-api cast-duckdns casty-caddy casty-api casty-duckdns jobify-caddy jobify-api jobify-duckdns 2>/dev/null || true
  docker compose -f docker-compose.prod.yml --profile duckdns --env-file .env up -d --force-recreate --remove-orphans"

sed -i.bak "s|^DOMAIN=.*|DOMAIN=${DOMAIN}|" "$ENV_FILE" || true
grep -q '^DOMAIN=' "$ENV_FILE" || echo "DOMAIN=${DOMAIN}" >> "$ENV_FILE"
rm -f "${ENV_FILE}.bak"

echo "==> Wait for HTTPS"
for i in $(seq 1 36); do
  if curl -fsS "https://${DOMAIN}/api/health" >/dev/null 2>&1; then
    curl -fsS "https://${DOMAIN}/api/health"; echo
    echo "Live: https://${DOMAIN}"
    exit 0
  fi
  sleep 5
done
echo "Still waiting on cert — check: curl -v https://${DOMAIN}/api/health"
exit 1
