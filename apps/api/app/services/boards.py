from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any, Optional
from html import unescape

import httpx
from sqlmodel import Session

from app.core.config import get_settings
from app.services.jobs import (
    _parse_iso,
    _parse_salary_text,
    _upsert_job,
    currency_for_location,
    seniority_rank,
)

USER_AGENT = "lernyra/0.1 (+local; job-aggregator)"


def _tokens(query: str) -> list[str]:
    return [t for t in re.split(r"[\s,/|+]+", query.strip().lower()) if len(t) >= 2]


def title_matches_query(query: str, title: str) -> bool:
    tokens = _tokens(query)
    if not tokens:
        return True
    hay = title or ""
    return all(re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", hay, re.I) for tok in tokens)


def soft_matches_query(query: str, title: str, description: str = "") -> bool:
    if title_matches_query(query, title):
        return True
    tokens = _tokens(query)
    if not tokens:
        return True
    hay = f"{title}\n{description}"
    return all(re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", hay, re.I) for tok in tokens)


def relevance_score(query: str, title: str) -> int:
    score = 0
    if title_matches_query(query, title):
        score += 100
        lower = title.lower()
        for tok in _tokens(query):
            idx = lower.find(tok)
            if idx >= 0:
                score += max(0, 30 - idx)
    score += (5 - seniority_rank(title)) * 10
    return score


def _strip_html(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", unescape(no_tags)).strip()


def _listing(job_id: Any, title: str, company: str, location: str, url: str, source: str) -> dict:
    return {
        "id": job_id,
        "title": title,
        "company": company or "",
        "location": location or "",
        "url": url,
        "source": source,
    }


async def _get_json(client: httpx.AsyncClient, url: str, **kwargs: Any) -> Any:
    resp = await client.get(url, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _save_payloads(session: Session, payloads: list[dict], query: str) -> list[dict]:
    listings: list[dict] = []
    seen: set[str] = set()
    for payload in payloads:
        url = (payload.get("url") or "").rstrip("/")
        if not url or url in seen:
            continue
        title = payload.get("title") or ""
        if query and not title_matches_query(query, title):
            continue
        seen.add(url)
        job = _upsert_job(session, payload)
        listings.append(
            _listing(job.id, title, payload.get("company", ""), payload.get("location", ""), url, payload["source"])
        )
    if payloads:
        session.commit()
    return listings


async def _collect_jobicy(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    tag = _tokens(query)[0] if _tokens(query) else ""
    urls = [f"https://jobicy.com/api/v2/remote-jobs?count={min(limit, 50)}"]
    if tag:
        urls.insert(0, f"https://jobicy.com/api/v2/remote-jobs?count={min(limit, 50)}&tag={tag}")

    payloads: list[dict] = []
    seen: set[str] = set()
    for url in urls:
        try:
            data = await _get_json(client, url)
        except Exception:
            continue
        for item in data.get("jobs") or []:
            title = item.get("jobTitle") or ""
            job_url = item.get("url") or ""
            if not title or not job_url or job_url in seen:
                continue
            if query and not title_matches_query(query, title):
                continue
            seen.add(job_url)
            payloads.append(
                {
                    "external_id": f"jobicy-{item.get('id') or job_url}",
                    "source": "jobicy",
                    "title": title,
                    "company": item.get("companyName") or "",
                    "location": item.get("jobGeo") or "Remote",
                    "description": _strip_html(item.get("jobDescription") or item.get("jobExcerpt") or ""),
                    "url": job_url,
                    "salary_min": None,
                    "salary_max": None,
                    "currency": "USD",
                    "posted_at": _parse_iso((item.get("pubDate") or "").replace(" ", "T")),
                }
            )
    return payloads


async def _collect_remotive(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    settings = get_settings()
    if not settings.remotive_enabled:
        return []

    endpoints = [
        "https://remotive.com/api/remote-jobs?limit=100",
        "https://remotive.com/api/remote-jobs?category=software-dev&limit=100",
        "https://remotive.com/api/remote-jobs?category=data&limit=100",
    ]
    payloads: list[dict] = []
    seen: set[str] = set()
    for url in endpoints:
        try:
            data = await _get_json(client, url)
        except Exception:
            continue
        for item in data.get("jobs") or []:
            title = item.get("title") or "Untitled"
            job_url = item.get("url") or ""
            ext = f"remotive-{item.get('id')}"
            if not job_url or ext in seen:
                continue
            if query and not title_matches_query(query, title):
                continue
            seen.add(ext)
            salary_min, salary_max, sal_currency = _parse_salary_text(item.get("salary") or "")
            payloads.append(
                {
                    "external_id": ext,
                    "source": "remotive",
                    "title": title,
                    "company": item.get("company_name") or "",
                    "location": item.get("candidate_required_location") or "Remote",
                    "description": _strip_html(item.get("description") or ""),
                    "url": job_url,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "currency": sal_currency,
                    "posted_at": _parse_iso(item.get("publication_date")),
                }
            )
            if len(payloads) >= limit:
                return payloads
    return payloads


async def _collect_remoteok(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    try:
        data = await _get_json(client, "https://remoteok.com/api")
    except Exception:
        return []

    payloads: list[dict] = []
    for item in data:
        if not isinstance(item, dict) or not item.get("position"):
            continue
        title = item.get("position") or ""
        if query and not title_matches_query(query, title):
            continue
        job_url = item.get("url") or item.get("apply_url") or ""
        if not job_url and item.get("id"):
            job_url = f"https://remoteok.com/remote-jobs/{item.get('id')}"
        if not job_url:
            continue
        payloads.append(
            {
                "external_id": f"remoteok-{item.get('id') or job_url}",
                "source": "remoteok",
                "title": title,
                "company": item.get("company") or "",
                "location": item.get("location") or "Remote",
                "description": _strip_html(item.get("description") or ""),
                "url": job_url,
                "salary_min": item.get("salary_min"),
                "salary_max": item.get("salary_max"),
                "currency": "USD",
                "posted_at": datetime.utcfromtimestamp(item["epoch"]) if item.get("epoch") else None,
            }
        )
        if len(payloads) >= limit:
            break
    return payloads


async def _collect_arbeitnow(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    params = {"search": query} if query else {}
    try:
        data = await _get_json(client, "https://www.arbeitnow.com/api/job-board-api", params=params)
    except Exception:
        return []

    payloads: list[dict] = []
    for item in data.get("data") or []:
        title = item.get("title") or ""
        if query and not title_matches_query(query, title):
            continue
        job_url = item.get("url") or ""
        if not job_url:
            continue
        payloads.append(
            {
                "external_id": f"arbeitnow-{item.get('slug') or job_url}",
                "source": "arbeitnow",
                "title": title,
                "company": item.get("company_name") or "",
                "location": item.get("location") or ("Remote" if item.get("remote") else ""),
                "description": _strip_html(item.get("description") or ""),
                "url": job_url,
                "salary_min": None,
                "salary_max": None,
                "currency": "EUR",
                "posted_at": datetime.utcfromtimestamp(item["created_at"]) if item.get("created_at") else None,
            }
        )
        if len(payloads) >= limit:
            break
    return payloads


async def _collect_himalayas(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    jobs: list[dict] = []
    try:
        for offset in (0, 100, 200):
            data = await _get_json(
                client,
                "https://himalayas.app/jobs/api",
                params={"limit": 100, "offset": offset},
            )
            batch = data.get("jobs") or []
            if not batch:
                break
            jobs.extend(batch)
    except Exception:
        return []

    payloads: list[dict] = []
    for item in jobs:
        title = item.get("title") or ""
        if query and not title_matches_query(query, title):
            continue
        job_url = item.get("applicationLink") or item.get("guid") or ""
        if not job_url:
            continue
        locs = item.get("locationRestrictions") or []
        location = ", ".join(locs) if isinstance(locs, list) and locs else "Remote"
        payloads.append(
            {
                "external_id": f"himalayas-{item.get('guid') or job_url}",
                "source": "himalayas",
                "title": title,
                "company": item.get("companyName") or "",
                "location": location,
                "description": _strip_html(item.get("excerpt") or ""),
                "url": job_url,
                "salary_min": item.get("minSalary"),
                "salary_max": item.get("maxSalary"),
                "currency": item.get("currency") or "USD",
                "posted_at": datetime.utcfromtimestamp(item["pubDate"]) if item.get("pubDate") else None,
            }
        )
        if len(payloads) >= limit:
            break
    return payloads


async def _collect_adzuna(client: httpx.AsyncClient, query: str, location: str, limit: int) -> list[dict]:
    settings = get_settings()
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        return []

    currency = currency_for_location(location)
    country = {
        "GBP": "gb",
        "EUR": "de",
        "CAD": "ca",
        "AUD": "au",
        "USD": "us",
    }.get(currency, "us")
    loc = (location or "").lower()
    if "ireland" in loc or "dublin" in loc:
        country = "ie"
        currency = "EUR"
    elif "netherlands" in loc or "amsterdam" in loc:
        country = "nl"
        currency = "EUR"
    elif "france" in loc or "paris" in loc:
        country = "fr"
        currency = "EUR"
    elif "germany" in loc or "berlin" in loc or "munich" in loc:
        country = "de"
        currency = "EUR"
    elif "poland" in loc or "warsaw" in loc:
        country = "pl"
        currency = "PLN"

    params = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "results_per_page": min(limit, 50),
        "what": query,
        "content-type": "application/json",
    }
    if location:
        params["where"] = location

    try:
        data = await _get_json(
            client,
            f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
            params=params,
        )
    except Exception:
        return []

    payloads: list[dict] = []
    for item in data.get("results", []):
        title = item.get("title") or "Untitled"
        if query and not title_matches_query(query, title):
            continue
        job_url = item.get("redirect_url") or ""
        if not job_url:
            continue
        payloads.append(
            {
                "external_id": f"adzuna-{item.get('id')}",
                "source": "adzuna",
                "title": title,
                "company": (item.get("company") or {}).get("display_name", ""),
                "location": (item.get("location") or {}).get("display_name", location or ""),
                "description": item.get("description") or "",
                "url": job_url,
                "salary_min": item.get("salary_min"),
                "salary_max": item.get("salary_max"),
                "currency": currency,
                "posted_at": _parse_iso(item.get("created")),
            }
        )
    return payloads


async def fetch_all_marketplaces(
    session: Session,
    query: str,
    location: str = "",
    per_source: int = 30,
) -> list[dict]:
    q = query.strip()
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=25.0, headers=headers) as client:
        collected = await asyncio.gather(
            _collect_jobicy(client, q, per_source),
            _collect_remotive(client, q, per_source),
            _collect_remoteok(client, q, per_source),
            _collect_arbeitnow(client, q, per_source),
            _collect_himalayas(client, q, per_source),
            _collect_adzuna(client, q, location, per_source),
            return_exceptions=True,
        )

    payloads: list[dict] = []
    for result in collected:
        if isinstance(result, Exception) or not result:
            continue
        payloads.extend(result)

    listings = _save_payloads(session, payloads, q)
    listings.sort(
        key=lambda item: (
            -relevance_score(q, item.get("title") or ""),
            seniority_rank(item.get("title") or ""),
            (item.get("title") or "").lower(),
        )
    )
    return listings


# Back-compat aliases used by older call sites
async def fetch_remotive_jobs(session: Session, query: str, limit: int = 40) -> list[dict]:
    async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": USER_AGENT}) as client:
        payloads = await _collect_remotive(client, query, limit)
    return _save_payloads(session, payloads, query)


async def fetch_adzuna_jobs(
    session: Session,
    query: str,
    location: str = "",
    limit: int = 30,
) -> list[dict]:
    async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": USER_AGENT}) as client:
        payloads = await _collect_adzuna(client, query, location, limit)
    return _save_payloads(session, payloads, query)
