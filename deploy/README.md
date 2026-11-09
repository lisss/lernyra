# Deploy Lernyra (free AWS + free domain + GitHub Actions)

**Stack:** GitHub Actions builds a Docker image → pushes to GHCR → EC2 pulls it.  
**Domain:** free `<elastic-ip>.sslip.io` (no signup) or optional DuckDNS + Caddy HTTPS.  
**Host:** AWS free-tier EC2 (`t3.micro` / `t2.micro`).

**Fast path (scripted):** after you export AWS keys, run:

```bash
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=us-east-1
./deploy/provision-ec2.sh
./deploy/finish-remote.sh   # starts app + sets GH Actions secrets if `gh` is logged in
```

> AWS free tier changed in mid-2025. New accounts get credits (~$100–$200 for up to 6 months). Older accounts may still have the classic 12‑month `t2.micro`/`t3.micro` offer. Watch Billing → Free Tier.

There is no lasting free custom `.com`. DuckDNS gives you a free hostname like `getbeacon.duckdns.org`.

---

## 1. Free domain (DuckDNS)

1. Sign in at [https://www.duckdns.org](https://www.duckdns.org)
2. Create a subdomain, e.g. `getbeacon` → `getbeacon.duckdns.org`
3. Copy your **token** (used in the server `.env`)

Leave the IP blank for now; the DuckDNS container on EC2 will set it.

---

## 2. AWS EC2 (free tier)

1. Create / sign in to AWS → **EC2 → Launch instance**
2. Name: `lernyra`
3. AMI: **Ubuntu Server 24.04 LTS**
4. Type: **t3.micro** (or **t2.micro** if that’s what Free Tier shows)
5. Key pair: create/download a `.pem` (you’ll use this for SSH + GitHub secret)
6. Network → security group inbound:
   - **22** from *your IP* (SSH)
   - **80** from `0.0.0.0/0` (HTTP / ACME)
   - **443** from `0.0.0.0/0` (HTTPS)
7. Storage: **30 GB gp3** (stay within free-tier disk if possible)
8. (Optional) Allocate an **Elastic IP** and associate it (free while attached to a running instance — IP won’t change on stop/start)
9. Launch

### Bootstrap Docker + app dir

SSH in:

```bash
ssh -i ~/Downloads/lernyra.pem ubuntu@YOUR_EC2_PUBLIC_IP
curl -fsSL https://raw.githubusercontent.com/lisss/lernyra/main/deploy/ec2-bootstrap.sh | sudo bash
```

Edit env:

```bash
nano /opt/lernyra/.env
```

Set at least:

```env
DOMAIN=getbeacon.duckdns.org
DUCKDNS_SUBDOMAIN=getbeacon
DUCKDNS_TOKEN=your-duckdns-token
IMAGE=ghcr.io/lisss/lernyra:latest
```

Make the GHCR package **public** (GitHub → Packages → `lernyra` → Package settings → Change visibility), **or** create a PAT with `read:packages` and put it in GitHub secrets as `GHCR_TOKEN` (+ `GHCR_USER`).

First start (after an image exists on GHCR — push `main` once first if needed):

```bash
cd /opt/lernyra
docker compose -f docker-compose.prod.yml --env-file .env pull
docker compose -f docker-compose.prod.yml --env-file .env up -d
```

Open `https://getbeacon.duckdns.org` (Caddy issues a Let’s Encrypt cert automatically).

---

## 3. GitHub Actions secrets & vars

Repo → **Settings → Secrets and variables → Actions**

| Kind | Name | Value |
|------|------|--------|
| Secret | `EC2_HOST` | Elastic IP or public DNS |
| Secret | `EC2_USER` | `ubuntu` |
| Secret | `EC2_SSH_KEY` | Full contents of the `.pem` |
| Secret | `GHCR_TOKEN` | (optional) PAT with `read:packages` if the image is private |
| Secret | `GHCR_USER` | (optional) GitHub username for that PAT |
| Variable | `DEPLOY_ENABLED` | `true` (enables the deploy job) |
| Variable | `APP_DIR` | optional, default `/opt/lernyra` |

On every push to `main`:

1. Build `linux/amd64` image
2. Push `ghcr.io/lisss/lernyra:latest` (+ short SHA tag)
3. If `DEPLOY_ENABLED=true`, SSH to EC2, `git pull`, `docker compose pull && up -d`

Until you set `DEPLOY_ENABLED=true`, pushes only publish the image (safe while you finish EC2 setup).

---

## 4. Sanity checks

```bash
# on EC2
docker compose -f /opt/lernyra/docker-compose.prod.yml --env-file /opt/lernyra/.env ps
curl -fsS https://getbeacon.duckdns.org/api/health
```

Local equivalent remains:

```bash
make up   # docker compose on your machine
```

---

## Cost / sizing notes

- **SQLite** is used in prod compose so a 1 GB micro instance stays alive (Postgres + API + Caddy often OOMs).
- Stop the instance when unused if you’re on credit-based free tier.
- After free credits / 12 months expire, a always-on `t3.micro` bills ~$7–10/mo + a little egress — or migrate to Render/Fly free tiers later.

---

## Later: more robust (same GHCR image)

This free path is intentionally thin. When you outgrow it, keep the **same Dockerfile / GHCR image** and swap the host:

| Now (free) | Next step |
|------------|-----------|
| Single EC2 + Docker Compose | ECS Fargate or Lightsail Containers |
| SQLite volume on disk | RDS Postgres (or Neon) — already supported via `DATABASE_URL` |
| DuckDNS + Caddy on-box | Route 53 + ACM + ALB (or Cloudflare) |
| SSH deploy from Actions | `aws ecs update-service` / Terraform |

No app rewrite required — only compose/infra and secrets change.
