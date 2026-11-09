# Lernyra

See what a job role needs — compare it to your CV or skills — and get a study plan with trusted books, courses, certifications, and interview prep.

**Live:** [https://getbeacon.duckdns.org](https://getbeacon.duckdns.org)

## Stack

| Layer | Tech |
|--------|------|
| Frontend | Vite + React + TypeScript |
| Backend | FastAPI (Python) |
| Database | SQLite locally / on free-tier EC2; Postgres optional |
| Deploy | GitHub Actions → GHCR → EC2 + Caddy + DuckDNS |

## Quick start (hot reload)

```bash
# Terminal 1 — API http://localhost:8001
make api

# Terminal 2 — UI http://localhost:3000
make web
```

Or Docker (rebuild to pick up code changes): `make up` → http://localhost:8000

## Deploy

Push to `main` builds and deploys automatically. See [deploy/README.md](deploy/README.md).

Public hostname: `getbeacon.duckdns.org` (SEO canonical; brand is Lernyra). Older DuckDNS names (`getmedeina`, `pathquire`, `getcast`) redirect permanently.

## SEO

- Canonical + Open Graph / Twitter meta on the homepage
- `/sitemap.xml` and `/robots.txt`
- Indexable role guides at `/roles/{slug}` (e.g. [/roles/python-developer](https://getbeacon.duckdns.org/roles/python-developer))
- Google Search Console HTML-file verification via `/google….html`

## MVP features

- Role search with typical skill requirements
- CV upload / skills → gaps vs the role
- Books, courses, certifications, interview prompts
- Curriculum + learning roadmap + estimated study time
- Learning list (saved TODOs)
