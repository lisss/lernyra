from __future__ import annotations

import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx

from app.core.config import get_settings
from app.models.schemas import ResourceOut, ResourceReview

USER_AGENT = "lernyra/1.0 (learning insights; +https://github.com/lisss/lernyra)"
TIMEOUT = 8.0

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SEC = 60 * 30

# Publishers and retailers only — Open Library links are rewritten, never shown.
_TRUSTED_HOST_SUFFIXES = (
    "goodreads.com",
    "amazon.com",
    "amazon.co.uk",
    "manning.com",
    "oreilly.com",
    "packtpub.com",
    "informit.com",
    "wiley.com",
    "apress.com",
    "nostarch.com",
    "pragprog.com",
    "pearson.com",
    "github.com",
    "githubusercontent.com",
    "stackoverflow.com",
    "stackexchange.com",
    "freecodecamp.org",
    "selectstarsql.com",
    "leetcode.com",
    "neetcode.io",
    "kubernetes.io",
    "developer.mozilla.org",
    "docs.python.org",
    "docs.djangoproject.com",
    "fastapi.tiangolo.com",
    "react.dev",
    "nextjs.org",
    "nodejs.org",
    "postgresql.org",
    "redis.io",
    "mongodb.com",
    "realpython.com",
    "learn.microsoft.com",
    "cloud.google.com",
    "docs.aws.amazon.com",
    "oracle.com",
    "youtube.com",
    "youtu.be",
)

# Correct well-known CS classics when catalogs have garbage years (e.g. Knuth ≠ 1922).
_CLASSIC_BOOKS: dict[str, dict[str, Any]] = {
    "the art of computer programming": {"year": 1968, "author": "knuth"},
    "introduction to algorithms": {"year": 1990, "author": "cormen"},
    "design patterns": {"year": 1994, "author": "gamma"},
    "clean code": {"year": 2008, "author": "martin"},
    "the pragmatic programmer": {"year": 1999, "author": "hunt"},
    "refactoring": {"year": 1999, "author": "fowler"},
    "code complete": {"year": 1993, "author": "mcconnell"},
    "structure and interpretation of computer programs": {"year": 1985, "author": "abelson"},
    "operating system concepts": {"year": 1983, "author": "silberschatz"},
    "computer networks": {"year": 1981, "author": "tanenbaum"},
    "compilers principles techniques and tools": {"year": 1986, "author": "aho"},
}


def _host_trusted(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    path = (urlparse(url).path or "").lower()
    if "google.com" in host and "/search" in path:
        return False
    return any(host == s or host.endswith("." + s) for s in _TRUSTED_HOST_SUFFIXES)


def _classic_meta(title: str) -> dict[str, Any] | None:
    key = re.sub(r"[^a-z0-9 ]+", "", (title or "").lower())
    key = re.sub(r"\s+", " ", key).strip()
    for name, meta in _CLASSIC_BOOKS.items():
        if name in key:
            return meta
    return None


def _sane_book_year(title: str, year: Any, _authors: list[str] | None = None) -> int | None:
    """Return a trusted publication year, or None when the catalog year is nonsense."""
    classic = _classic_meta(title)
    if classic:
        return int(classic["year"])
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None
    current = datetime.now(timezone.utc).year
    # CS/programming catalogs with years before ~1950 are almost always wrong.
    if y < 1950 or y > current + 1:
        return None
    return y


def _book_quality_ok(
    *,
    title: str,
    year: int | None,
    rating: float | None,
    rating_count: int,
    edition_count: int = 0,
) -> bool:
    """Keep high-rated / classic / well-editioned books; drop junk catalog hits."""
    if _classic_meta(title):
        return True
    if year is None:
        return bool(rating and rating >= 4.2 and rating_count >= 15)
    if rating and rating >= 4.0 and rating_count >= 8:
        return True
    if rating and rating >= 4.5 and rating_count >= 3:
        return True
    if edition_count >= 8 and year >= 1980:
        return True
    if year >= 2015 and (rating is None or rating >= 3.5):
        return True
    return False


def _github_fresh(pushed_at: str | None, *, max_years: float = 2.0) -> bool:
    if not pushed_at:
        return False
    try:
        # GitHub returns ISO timestamps like 2024-01-15T12:00:00Z
        ts = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    age_days = (datetime.now(timezone.utc) - ts).days
    return age_days <= int(max_years * 365)


def _book_store_url(title: str, authors: list[str] | None = None, publisher: str = "") -> str:
    pub = (publisher or "").lower()
    author = (authors or [""])[0]
    q = quote_plus(f"{title} {author}".strip())
    title_q = quote_plus(title)
    if "manning" in pub:
        return f"https://www.manning.com/search?q={title_q}"
    if "o'reilly" in pub or "oreilly" in pub:
        return f"https://www.oreilly.com/search/?q={title_q}"
    if "packt" in pub:
        return f"https://www.packtpub.com/search?query={title_q}"
    if "nostarch" in pub or "no starch" in pub:
        return f"https://nostarch.com/?s={title_q}"
    if "pragmatic" in pub or "pragprog" in pub:
        return f"https://pragprog.com/search/?q={title_q}"
    if "wiley" in pub:
        return f"https://www.wiley.com/en-us/search?pq={title_q}"
    if "addison" in pub or "pearson" in pub or "prentice" in pub:
        return f"https://www.informit.com/search/index.aspx?query={title_q}"
    return f"https://www.goodreads.com/search?utf8=%E2%9C%93&query={q}"


_TRUSTED_BOOK_CATALOG: list[dict[str, Any]] = [
    {
        "keys": ("python", "backend", "software"),
        "title": "Fluent Python",
        "author": "Luciano Ramalho",
        "url": "https://www.oreilly.com/library/view/fluent-python-2nd/9781492056348/",
        "provider": "O'Reilly",
        "year": 2022,
        "rating": 4.7,
        "rating_count": 1200,
        "hours": 40,
        "desc": "Deep dive into idiomatic Python — O'Reilly.",
    },
    {
        "keys": ("python",),
        "title": "Learning Python",
        "author": "Mark Lutz",
        "url": "https://www.oreilly.com/library/view/learning-python-5th/9781449355722/",
        "provider": "O'Reilly",
        "year": 2013,
        "rating": 4.3,
        "rating_count": 800,
        "hours": 45,
        "desc": "Comprehensive Python fundamentals — O'Reilly.",
    },
    {
        "keys": ("python", "clean code", "software"),
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "url": "https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350882",
        "provider": "Amazon / Pearson",
        "year": 2008,
        "rating": 4.4,
        "rating_count": 5000,
        "hours": 28,
        "desc": "Classic craftsmanship handbook.",
    },
    {
        "keys": ("algorithm", "algorithms", "data structure", "interview", "leetcode"),
        "title": "Introduction to Algorithms (CLRS)",
        "author": "Cormen et al.",
        "url": "https://www.amazon.com/Introduction-Algorithms-fourth-Thomas-Cormen/dp/026204630X",
        "provider": "Amazon / MIT Press",
        "year": 2022,
        "rating": 4.6,
        "rating_count": 3000,
        "hours": 60,
        "desc": "Standard algorithms reference (4th ed.).",
    },
    {
        "keys": ("algorithm", "algorithms", "interview"),
        "title": "Grokking Algorithms",
        "author": "Aditya Bhargava",
        "url": "https://www.manning.com/books/grokking-algorithms-second-edition",
        "provider": "Manning",
        "year": 2024,
        "rating": 4.6,
        "rating_count": 2500,
        "hours": 18,
        "desc": "Friendly illustrated algorithms intro — Manning.",
    },
    {
        "keys": ("system design", "backend", "architecture", "distributed"),
        "title": "Designing Data-Intensive Applications",
        "author": "Martin Kleppmann",
        "url": "https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/",
        "provider": "O'Reilly",
        "year": 2017,
        "rating": 4.8,
        "rating_count": 4000,
        "hours": 45,
        "desc": "Modern data systems / backend architecture — O'Reilly.",
    },
    {
        "keys": ("sql", "database", "postgres", "backend"),
        "title": "SQL Queries for Mere Mortals",
        "author": "John L. Viescas",
        "url": "https://www.amazon.com/SQL-Queries-Mere-Mortals-Hands/dp/0134858335",
        "provider": "Amazon / Addison-Wesley",
        "year": 2018,
        "rating": 4.5,
        "rating_count": 600,
        "hours": 22,
        "desc": "Practical SQL query skills.",
    },
    {
        "keys": ("java", "spring", "backend"),
        "title": "Effective Java",
        "author": "Joshua Bloch",
        "url": "https://www.amazon.com/Effective-Java-Joshua-Bloch/dp/0134685997",
        "provider": "Amazon / Addison-Wesley",
        "year": 2018,
        "rating": 4.7,
        "rating_count": 2000,
        "hours": 30,
        "desc": "Essential Java best practices.",
    },
    {
        "keys": ("javascript", "typescript", "frontend", "node"),
        "title": "You Don't Know JS Yet",
        "author": "Kyle Simpson",
        "url": "https://www.amazon.com/You-Dont-Know-JS-Yet/dp/1098124033",
        "provider": "Amazon / O'Reilly",
        "year": 2020,
        "rating": 4.6,
        "rating_count": 900,
        "hours": 25,
        "desc": "Deep JavaScript mechanics.",
    },
    {
        "keys": ("design pattern", "software", "oop", "architecture"),
        "title": "Design Patterns (GoF)",
        "author": "Gamma et al.",
        "url": "https://www.amazon.com/Design-Patterns-Elements-Reusable-Object-Oriented/dp/0201633612",
        "provider": "Amazon / Addison-Wesley",
        "year": 1994,
        "rating": 4.5,
        "rating_count": 4000,
        "hours": 35,
        "desc": "Foundational object-oriented patterns.",
    },
    {
        "keys": ("refactor", "clean", "software"),
        "title": "Refactoring",
        "author": "Martin Fowler",
        "url": "https://www.amazon.com/Refactoring-Improving-Existing-Addison-Wesley-Signature/dp/0134757599",
        "provider": "Amazon / Addison-Wesley",
        "year": 2018,
        "rating": 4.6,
        "rating_count": 1500,
        "hours": 30,
        "desc": "Improving existing code systematically.",
    },
    {
        "keys": ("pragmatic", "software", "career"),
        "title": "The Pragmatic Programmer",
        "author": "David Thomas & Andrew Hunt",
        "url": "https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/",
        "provider": "The Pragmatic Bookshelf",
        "year": 2019,
        "rating": 4.7,
        "rating_count": 3500,
        "hours": 20,
        "desc": "Timeless software craft advice.",
    },
]


def _trusted_books_for_query(role: str, skills: list[str], limit: int = 6) -> list[ResourceOut]:
    hay = f"{role} {' '.join(skills)}".lower()
    picked: list[ResourceOut] = []
    for entry in _TRUSTED_BOOK_CATALOG:
        if not any(k in hay for k in entry["keys"]):
            continue
        hours = float(entry["hours"])
        skills_tags = _skills_from_query(hay) or list(entry["keys"][:2])
        value = compute_value_score(
            rating=entry.get("rating"),
            rating_count=entry.get("rating_count"),
            skill_hits=_skill_hits(skills_tags, hay, entry["title"], entry["desc"]),
        )
        value += 6.0  # curated catalog outranks a raw search hit
        picked.append(
            ResourceOut(
                kind="book",
                title=entry["title"],
                url=entry["url"],
                provider=entry["provider"],
                skills=skills_tags,
                description=_clean(f"{entry['author']} ({entry['year']}) — {entry['desc']}"),
                estimated_hours=hours,
                value_score=round(value, 3),
                rating=entry.get("rating"),
                rating_count=entry.get("rating_count"),
                study_tip=_study_tip("book", hours),
            )
        )
    if not picked:
        for entry in _TRUSTED_BOOK_CATALOG[:3]:
            hours = float(entry["hours"])
            picked.append(
                ResourceOut(
                    kind="book",
                    title=entry["title"],
                    url=entry["url"],
                    provider=entry["provider"],
                    skills=_skills_from_query(hay),
                    description=_clean(f"{entry['author']} ({entry['year']}) — {entry['desc']}"),
                    estimated_hours=hours,
                    value_score=20.0,
                    rating=entry.get("rating"),
                    rating_count=entry.get("rating_count"),
                    study_tip=_study_tip("book", hours),
                )
            )
    return rank_resources(_dedupe(picked))[:limit]


def _algorithm_practice_links(role: str, skills: list[str]) -> list[ResourceOut]:
    hay = f"{role} {' '.join(skills)}".lower()
    algo_keys = (
        "algorithm",
        "algorithms",
        "leetcode",
        "neetcode",
        "data structure",
        "datastructure",
        "interview",
        "coding interview",
        "dsa",
        "competitive",
    )
    role_keys = ("software", "backend", "frontend", "full stack", "engineer", "developer", "sde")
    if not (any(k in hay for k in algo_keys) or any(k in hay for k in role_keys)):
        return []
    tip = _study_tip("course", 20)
    return [
        ResourceOut(
            kind="course",
            title="NeetCode — roadmap & practice problems",
            url="https://neetcode.io/roadmap",
            provider="NeetCode",
            skills=["Algorithms", "Interview"],
            description="Curated DSA roadmap mapped to common interview patterns.",
            estimated_hours=40,
            value_score=48,
            rating=4.9,
            rating_count=50000,
            study_tip=tip,
        ),
        ResourceOut(
            kind="course",
            title="LeetCode — problem set & study plans",
            url="https://leetcode.com/problemset/",
            provider="LeetCode",
            skills=["Algorithms", "Interview"],
            description="Industry-standard coding interview practice.",
            estimated_hours=50,
            value_score=46,
            rating=4.7,
            rating_count=100000,
            study_tip=tip,
        ),
        ResourceOut(
            kind="course",
            title="NeetCode.io — practice list",
            url="https://neetcode.io/practice",
            provider="NeetCode",
            skills=["Algorithms"],
            description="Focused problem list covering Blind 75 / NeetCode 150.",
            estimated_hours=35,
            value_score=44,
            rating=4.8,
            rating_count=20000,
            study_tip=tip,
        ),
    ]


def filter_trusted_resources(
    items: list[ResourceOut],
    *,
    blocked_urls: set[str] | None = None,
) -> list[ResourceOut]:
    blocked = {u.rstrip("/").lower() for u in (blocked_urls or set())}
    out: list[ResourceOut] = []
    for item in items:
        url = (item.url or "").rstrip("/")
        if not _host_trusted(url):
            continue
        if url.lower() in blocked:
            continue
        out.append(item)
    return out


def _cache_get(key: str) -> Any | None:
    hit = _CACHE.get(key)
    if not hit:
        return None
    expires, value = hit
    if time.time() > expires:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    _CACHE[key] = (time.time() + _CACHE_TTL_SEC, value)


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )


def _clean(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _queries(role: str, stack: list[str], gaps: list[str]) -> list[str]:
    role = role.strip() or "software engineer"
    parts: list[str] = []
    for skill in stack[:4]:
        parts.append(f"{skill} {role}")
        parts.append(f"{skill} programming")
    for skill in gaps[:4]:
        parts.append(f"{skill} for {role}")
        parts.append(skill)
    if not parts:
        parts.append(role)
        parts.append(f"{role} interview")
    seen: set[str] = set()
    out: list[str] = []
    for q in parts:
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out[:6]


def _skills_from_query(query: str) -> list[str]:
    stop = {"for", "and", "the", "with", "a", "an", "to", "of", "in", "on"}
    tokens = [
        t.strip(".,")
        for t in query.replace("/", " ").split()
        if len(t.strip(".,")) > 1 and t.lower() not in stop
    ]
    return tokens[:3]


def _book_hours(pages: int | None) -> float:
    if pages and pages > 40:
        # ~20 pages/hour of focused technical reading, notes included.
        return round(max(8.0, min(60.0, pages / 20.0)), 1)
    return 25.0


def _study_tip(kind: str, hours: float | None) -> str:
    h = hours or 12
    if kind == "book":
        return (
            f"Read in 45–60 min sessions (~{max(1, int(h / 8))} chapters/week). "
            "Take notes on patterns you can apply at work; skip chapters you already know."
        )
    if kind == "course":
        return (
            f"Block {min(2, max(1, int(h / 6)))} focused sessions/week. "
            "Pause to re-implement examples yourself before moving on."
        )
    if kind == "certification":
        return (
            "Skim the exam outline first, study weak domains, then do timed practice tests "
            "in the last 20% of the estimate."
        )
    if kind == "interview":
        return (
            "Write your own answer first, then compare. Rehearse aloud once; store a short cheat-card."
        )
    return "Schedule deliberate practice; prefer depth over skimming."


def compute_value_score(
    *,
    rating: float | None = None,
    rating_count: int | None = None,
    stars: int | None = None,
    votes: int | None = None,
    skill_hits: int = 0,
    learningish: bool = False,
) -> float:
    """Single comparable score: relevance first, then community quality."""
    score = 1.0 + skill_hits * 8.0
    if rating is not None:
        score += float(rating) * 3.0
        score += math.log10((rating_count or 0) + 1) * 2.0
    if stars is not None:
        score += math.log10(stars + 1) * 2.5
        if learningish:
            score += 5.0
    if votes is not None:
        score += math.log10(max(votes, 0) + 1) * 3.0
    return round(score, 3)


def _skill_hits(skills: list[str], query: str, title: str = "", desc: str = "") -> int:
    hay = f"{query} {title} {desc} {' '.join(skills)}".lower()
    hits = 0
    for token in _skills_from_query(query):
        if token.lower() in hay:
            hits += 1
    return hits


def _fetch_community_reviews(title: str, limit: int = 5) -> list[ResourceReview]:
    title = (title or "").strip()
    if not title or len(title) < 3:
        return []
    cache_key = f"reviews:{title.lower()[:80]}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    reviews: list[ResourceReview] = []

    try:
        with _client() as client:
            res = client.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "query": title[:120],
                    "tags": "(story,comment)",
                    "hitsPerPage": limit,
                },
            )
            if res.status_code < 400:
                for hit in res.json().get("hits") or []:
                    text = (hit.get("comment_text") or hit.get("title") or hit.get("story_title") or "").strip()
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = _clean(text, 220)
                    if not text:
                        continue
                    object_id = hit.get("objectID") or ""
                    story_id = hit.get("story_id") or object_id
                    url = (
                        f"https://news.ycombinator.com/item?id={story_id}"
                        if story_id
                        else (hit.get("url") or "")
                    )
                    points = hit.get("points")
                    rating = None
                    if isinstance(points, (int, float)) and points >= 0:
                        # Map HN points loosely onto a 1–5 display scale.
                        rating = round(min(5.0, 2.5 + math.log10(points + 1)), 1)
                    reviews.append(
                        ResourceReview(
                            author=hit.get("author") or "HN user",
                            rating=rating,
                            comment=text,
                            url=url,
                            source="Hacker News",
                        )
                    )
    except Exception:
        pass

    if len(reviews) < limit:
        try:
            with _client() as client:
                res = client.get(
                    "https://www.reddit.com/search.json",
                    params={"q": title[:100], "sort": "top", "limit": limit, "t": "all"},
                    headers={"User-Agent": USER_AGENT},
                )
                if res.status_code < 400:
                    children = ((res.json().get("data") or {}).get("children")) or []
                    for child in children:
                        data = child.get("data") or {}
                        text = _clean(data.get("title") or data.get("selftext") or "", 220)
                        if not text:
                            continue
                        permalink = data.get("permalink") or ""
                        url = f"https://www.reddit.com{permalink}" if permalink else (data.get("url") or "")
                        ups = data.get("ups") or data.get("score") or 0
                        rating = None
                        if isinstance(ups, (int, float)) and ups > 0:
                            rating = round(min(5.0, 2.0 + math.log10(ups + 1)), 1)
                        reviews.append(
                            ResourceReview(
                                author=data.get("author") or "reddit",
                                rating=rating,
                                comment=text,
                                url=url,
                                source="Reddit",
                            )
                        )
                        if len(reviews) >= limit:
                            break
        except Exception:
            pass

    seen: set[str] = set()
    out: list[ResourceReview] = []
    for rev in reviews:
        key = rev.comment[:80].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(rev)
        if len(out) >= limit:
            break
    _cache_set(cache_key, out)
    return out


def _attach_reviews(items: list[ResourceOut], *, per_item: int = 5) -> list[ResourceOut]:
    if not items:
        return items

    def enrich(item: ResourceOut) -> ResourceOut:
        reviews = _fetch_community_reviews(item.title, limit=per_item)
        return item.model_copy(update={"reviews": reviews})

    with ThreadPoolExecutor(max_workers=min(4, len(items))) as pool:
        return list(pool.map(enrich, items))


def _fetch_open_library_books(query: str, limit: int = 4) -> list[ResourceOut]:
    cache_key = f"ol:{query}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    search = f"({query}) AND (programming OR software OR engineering OR computer)"
    url = "https://openlibrary.org/search.json"
    params = {
        "q": search,
        "limit": max(limit * 3, 8),
        "fields": (
            "key,title,author_name,first_publish_year,subject,language,"
            "ratings_average,ratings_count,number_of_pages_median,edition_count"
        ),
    }
    results: list[ResourceOut] = []
    try:
        with _client() as client:
            res = client.get(url, params=params)
            res.raise_for_status()
            docs = res.json().get("docs") or []
    except Exception:
        return []

    for doc in docs:
        title = (doc.get("title") or "").strip()
        if not title:
            continue
        subjects = " ".join(doc.get("subject") or []).lower()
        title_l = title.lower()
        technical = any(
            token in subjects or token in title_l
            for token in (
                "programming",
                "software",
                "computer",
                "engineering",
                "python",
                "java",
                "haskell",
                "backend",
                "web",
                "database",
                "api",
            )
        )
        if subjects and not technical:
            continue
        authors = doc.get("author_name") or []
        work_key = doc.get("key") or ""
        book_url = f"https://openlibrary.org{work_key}" if work_key else ""
        if not _host_trusted(book_url):
            continue
        year = _sane_book_year(title, doc.get("first_publish_year"), authors)
        pages = doc.get("number_of_pages_median")
        rating = doc.get("ratings_average")
        rating_count = int(doc.get("ratings_count") or 0)
        if isinstance(rating, (int, float)):
            rating = round(float(rating), 2)
        else:
            rating = None
        editions = int(doc.get("edition_count") or 0)
        if not _book_quality_ok(
            title=title,
            year=year,
            rating=rating,
            rating_count=rating_count,
            edition_count=editions,
        ):
            continue
        hours = _book_hours(int(pages) if pages else None)
        skills = _skills_from_query(query)
        desc = ", ".join(authors[:2])
        if year:
            desc = f"{desc} ({year})" if desc else str(year)
        if pages:
            desc = f"{desc} · ~{pages} pages" if desc else f"~{pages} pages"
        hits = _skill_hits(skills, query, title, f"{desc} {subjects}")
        value = compute_value_score(
            rating=rating,
            rating_count=rating_count,
            skill_hits=hits,
        )
        value += math.log10(editions + 1) * 0.8
        if _classic_meta(title):
            value += 8.0
        if hits == 0 and rating and rating >= 4.0:
            value *= 0.55
        results.append(
            ResourceOut(
                kind="book",
                title=title,
                url=book_url,
                provider="Open Library",
                skills=skills,
                description=_clean(desc or "Book match for your role and skills."),
                estimated_hours=hours,
                value_score=round(value, 3),
                rating=rating,
                rating_count=rating_count if rating_count else None,
                study_tip=_study_tip("book", hours),
            )
        )
        if len(results) >= limit:
            break
    results.sort(key=lambda r: r.value_score, reverse=True)
    _cache_set(cache_key, results)
    return results


def _fetch_google_books(query: str, limit: int = 4) -> list[ResourceOut]:
    settings = get_settings()
    key = (settings.google_books_api_key or "").strip()
    cache_key = f"gbooks:{bool(key)}:{query}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params: dict[str, Any] = {
        "q": f"{query} programming",
        "maxResults": max(limit, 5),
        "printType": "books",
        "orderBy": "relevance",
    }
    if key:
        params["key"] = key
    try:
        with _client() as client:
            res = client.get("https://www.googleapis.com/books/v1/volumes", params=params)
            if res.status_code >= 400:
                return []
            items = res.json().get("items") or []
    except Exception:
        return []

    results: list[ResourceOut] = []
    for item in items:
        info = item.get("volumeInfo") or {}
        title = (info.get("title") or "").strip()
        if not title:
            continue
        authors = info.get("authors") or []
        publisher = info.get("publisher") or ""
        # Never link to Open Library / raw Google Books pages — use trusted stores.
        link = _book_store_url(title, authors, publisher)
        if not _host_trusted(link):
            continue
        published = (info.get("publishedDate") or "")[:4]
        year = _sane_book_year(title, published or None, authors)
        pages = info.get("pageCount")
        rating = info.get("averageRating")
        rating_count = int(info.get("ratingsCount") or 0)
        if isinstance(rating, (int, float)):
            rating = round(float(rating), 2)
        else:
            rating = None
        if not _book_quality_ok(
            title=title,
            year=year,
            rating=rating,
            rating_count=rating_count,
            edition_count=0,
        ):
            continue
        hours = _book_hours(int(pages) if pages else None)
        skills = _skills_from_query(query)
        desc = info.get("description") or ", ".join(authors[:2])
        if year:
            desc = f"{desc} ({year})" if desc else str(year)
        store = urlparse(link).hostname or "bookstore"
        provider = (
            "Manning"
            if "manning.com" in store
            else "O'Reilly"
            if "oreilly.com" in store
            else "Amazon"
            if "amazon." in store
            else "Goodreads"
        )
        value = compute_value_score(
            rating=rating,
            rating_count=rating_count,
            skill_hits=_skill_hits(skills, query, title, desc),
        )
        if _classic_meta(title):
            value += 8.0
        results.append(
            ResourceOut(
                kind="book",
                title=title,
                url=link,
                provider=provider,
                skills=skills,
                description=_clean(desc),
                estimated_hours=hours,
                value_score=round(value, 3),
                rating=rating,
                rating_count=rating_count if rating_count else None,
                study_tip=_study_tip("book", hours),
            )
        )
    results.sort(key=lambda r: r.value_score, reverse=True)
    results = results[:limit]
    _cache_set(cache_key, results)
    return results


def _fetch_github_learning(query: str, limit: int = 4) -> list[ResourceOut]:
    settings = get_settings()
    cache_key = f"gh:{query}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    q = f"{query} (tutorial OR course OR roadmap OR learn OR handbook)"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = (settings.github_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        with _client() as client:
            res = client.get(
                "https://api.github.com/search/repositories",
                params={"q": q, "sort": "stars", "order": "desc", "per_page": max(limit * 2, 5)},
                headers=headers,
            )
            if res.status_code >= 400:
                res = client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": f"{query} tutorial",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": max(limit * 2, 5),
                    },
                    headers=headers,
                )
                if res.status_code >= 400:
                    return []
            items = res.json().get("items") or []
    except Exception:
        return []

    skip_names = {
        "python/cpython",
        "golang/go",
        "rust-lang/rust",
        "openjdk/jdk",
        "dotnet/runtime",
        "torvalds/linux",
    }
    results: list[ResourceOut] = []
    for item in items:
        name = (item.get("full_name") or item.get("name") or "").strip()
        html_url = item.get("html_url") or ""
        if not name or not html_url:
            continue
        if name.lower() in skip_names:
            continue
        stars = int(item.get("stargazers_count") or 0)
        name_l = name.lower()
        desc = item.get("description") or "GitHub learning resource"
        desc_l = desc.lower()
        if not _host_trusted(html_url):
            continue
        if not _github_fresh(item.get("pushed_at"), max_years=2.0):
            continue
        learningish = any(
            token in name_l or token in desc_l
            for token in (
                "roadmap",
                "awesome",
                "tutorial",
                "course",
                "learn",
                "handbook",
                "guide",
                "study",
                "30-days",
                "bootcamp",
                "primer",
                "for-beginners",
                "exercises",
            )
        )
        if not learningish:
            continue
        if stars > 80_000 and "primer" not in name_l and "awesome" not in name_l:
            continue
        hours = 8.0 if stars < 500 else (12.0 if stars < 5000 else 18.0)
        if "roadmap" in name_l or "awesome" in name_l:
            hours = 10.0
        skills = _skills_from_query(query)
        # Stars as a 1–5 “rating” proxy for UI.
        rating = round(min(5.0, 2.0 + math.log10(stars + 1)), 2) if stars else None
        value = compute_value_score(
            stars=stars,
            rating=rating,
            rating_count=stars,
            skill_hits=_skill_hits(skills, query, name, desc),
            learningish=True,
        )
        results.append(
            ResourceOut(
                kind="course",
                title=name,
                url=html_url,
                provider="GitHub",
                skills=skills,
                description=_clean(f"★ {stars} — {desc}"),
                estimated_hours=hours,
                value_score=round(value, 3),
                rating=rating,
                rating_count=stars if stars else None,
                study_tip=_study_tip("course", hours),
            )
        )
        if len(results) >= limit:
            break
    results.sort(key=lambda r: r.value_score, reverse=True)
    _cache_set(cache_key, results)
    return results


def _fetch_youtube_courses(query: str, limit: int = 4) -> list[ResourceOut]:
    settings = get_settings()
    api_key = (settings.youtube_api_key or "").strip()
    if not api_key:
        return []

    cache_key = f"yt:{query}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params = {
        "part": "snippet",
        "type": "video",
        "maxResults": limit,
        "q": f"{query} course tutorial",
        "key": api_key,
        "safeSearch": "moderate",
        "relevanceLanguage": "en",
    }
    try:
        with _client() as client:
            res = client.get("https://www.googleapis.com/youtube/v3/search", params=params)
            if res.status_code >= 400:
                return []
            items = res.json().get("items") or []
    except Exception:
        return []

    results: list[ResourceOut] = []
    for item in items:
        snippet = item.get("snippet") or {}
        video_id = (item.get("id") or {}).get("videoId")
        title = (snippet.get("title") or "").strip()
        if not video_id or not title:
            continue
        hours = 8.0
        skills = _skills_from_query(query)
        desc = snippet.get("description") or "Video course / tutorial"
        value = compute_value_score(skill_hits=_skill_hits(skills, query, title, desc)) + 5.0
        results.append(
            ResourceOut(
                kind="course",
                title=title,
                url=f"https://www.youtube.com/watch?v={video_id}",
                provider=snippet.get("channelTitle") or "YouTube",
                skills=skills,
                description=_clean(desc),
                estimated_hours=hours,
                value_score=round(value, 3),
                study_tip=_study_tip("course", hours),
            )
        )
    results.sort(key=lambda r: r.value_score, reverse=True)
    _cache_set(cache_key, results)
    return results


def _fetch_stack_interview(query: str, limit: int = 4) -> list[ResourceOut]:
    cache_key = f"so:{query}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params = {
        "order": "desc",
        "sort": "votes",
        "site": "stackoverflow",
        "pagesize": limit,
        "filter": "default",
    }
    token = re.sub(r"[^a-z0-9.+#]", "", query.lower().split()[0] if query else "")
    url = "https://api.stackexchange.com/2.3/search/advanced"
    if token and len(token) >= 2:
        params["tagged"] = token[:25]
        params["title"] = "interview"
    else:
        params["q"] = f"{query} interview"
        params["title"] = "interview"

    try:
        with _client() as client:
            res = client.get(url, params=params)
            if res.status_code >= 400:
                return []
            items = res.json().get("items") or []
    except Exception:
        return []

    results: list[ResourceOut] = []
    for item in items:
        title = (item.get("title") or "").strip()
        link = item.get("link") or ""
        if not title or not link:
            continue
        title = (
            title.replace("&quot;", '"')
            .replace("&#39;", "'")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )
        score = int(item.get("score") or 0)
        skills = _skills_from_query(query)
        rating = round(min(5.0, 2.0 + math.log10(max(score, 0) + 1)), 2) if score else None
        value = compute_value_score(
            votes=score,
            rating=rating,
            rating_count=score,
            skill_hits=_skill_hits(skills, query, title),
        )
        results.append(
            ResourceOut(
                kind="interview",
                title=title,
                url=link,
                provider="Stack Overflow",
                skills=skills,
                description=_clean(f"Score {score} — community Q&A for interview prep."),
                estimated_hours=1.5,
                value_score=round(value, 3),
                rating=rating,
                rating_count=score if score else None,
                study_tip=_study_tip("interview", 1.5),
            )
        )
    results.sort(key=lambda r: r.value_score, reverse=True)
    _cache_set(cache_key, results)
    return results


def _fetch_certification_pages(query: str, limit: int = 3) -> list[ResourceOut]:
    cache_key = f"cert:{query}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results: list[ResourceOut] = []
    cert_query = f"{query} certification"

    for book in _trusted_books_for_query(cert_query, [query], limit=2):
        hours = book.estimated_hours or 30
        results.append(
            book.model_copy(
                update={
                    "kind": "certification",
                    "description": _clean(book.description or "Certification-oriented material"),
                    "estimated_hours": max(hours, 20),
                    "study_tip": _study_tip("certification", max(hours, 20)),
                }
            )
        )

    for repo in _fetch_github_learning(f"{query} certification exam", limit=2):
        results.append(
            repo.model_copy(
                update={
                    "kind": "certification",
                    "description": _clean(repo.description or "Certification study repo"),
                    "estimated_hours": repo.estimated_hours or 20,
                    "study_tip": _study_tip("certification", repo.estimated_hours or 20),
                }
            )
        )

    results = rank_resources(filter_trusted_resources(_dedupe(results)))[:limit]
    _cache_set(cache_key, results)
    return results


def _dedupe(items: list[ResourceOut]) -> list[ResourceOut]:
    seen: set[str] = set()
    out: list[ResourceOut] = []
    for item in items:
        key = (item.url or item.title).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def rank_resources(items: list[ResourceOut]) -> list[ResourceOut]:
    return sorted(items, key=lambda r: (r.value_score, r.rating or 0, r.rating_count or 0), reverse=True)


def _merge_queries(
    fetcher,
    queries: list[str],
    *,
    per_query: int,
    limit: int,
) -> list[ResourceOut]:
    collected: list[ResourceOut] = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(queries)))) as pool:
        futures = {pool.submit(fetcher, q, per_query): q for q in queries}
        for fut in as_completed(futures):
            try:
                collected.extend(fut.result() or [])
            except Exception:
                continue
    return rank_resources(_dedupe(collected))[:limit]


def _fallback_courses(role: str, skills: list[str], limit: int = 6) -> list[ResourceOut]:
    catalog: list[tuple[tuple[str, ...], ResourceOut]] = [
        (
            ("python", "backend", "django", "flask", "fastapi"),
            ResourceOut(
                kind="course",
                title="freeCodeCamp — Python for Everybody / Backend",
                url="https://www.freecodecamp.org/news/python-for-everybody/",
                provider="freeCodeCamp",
                skills=["Python"],
                description="Free structured Python path with projects.",
                estimated_hours=20,
                value_score=40,
                rating=4.8,
                rating_count=10000,
                study_tip=_study_tip("course", 20),
            ),
        ),
        (
            ("python",),
            ResourceOut(
                kind="course",
                title="Asabeneh/30-Days-Of-Python",
                url="https://github.com/Asabeneh/30-Days-Of-Python",
                provider="GitHub",
                skills=["Python"],
                description="Day-by-day Python exercises (free).",
                estimated_hours=30,
                value_score=38,
                rating=4.9,
                rating_count=40000,
                study_tip=_study_tip("course", 30),
            ),
        ),
        (
            ("sql", "database", "postgres", "backend"),
            ResourceOut(
                kind="course",
                title="Select Star SQL — interactive SQL course",
                url="https://selectstarsql.com/",
                provider="Select Star SQL",
                skills=["SQL"],
                description="Free interactive SQL curriculum.",
                estimated_hours=10,
                value_score=36,
                rating=4.7,
                rating_count=2000,
                study_tip=_study_tip("course", 10),
            ),
        ),
        (
            ("system design", "backend", "architecture"),
            ResourceOut(
                kind="course",
                title="donnemartin/system-design-primer",
                url="https://github.com/donnemartin/system-design-primer",
                provider="GitHub",
                skills=["System Design"],
                description="Widely used free system-design study guide.",
                estimated_hours=18,
                value_score=42,
                rating=5.0,
                rating_count=250000,
                study_tip=_study_tip("course", 18),
            ),
        ),
        (
            ("javascript", "frontend", "react", "node"),
            ResourceOut(
                kind="course",
                title="freeCodeCamp — Responsive Web / JS Algorithms",
                url="https://www.freecodecamp.org/learn/",
                provider="freeCodeCamp",
                skills=["JavaScript"],
                description="Free full-stack curriculum with certifications.",
                estimated_hours=40,
                value_score=37,
                rating=4.8,
                rating_count=50000,
                study_tip=_study_tip("course", 40),
            ),
        ),
        (
            ("java", "spring", "backend"),
            ResourceOut(
                kind="course",
                title="Java Programming — freeCodeCamp / OpenJDK trail",
                url="https://www.freecodecamp.org/news/learn-java-free-java-courses-for-beginners/",
                provider="freeCodeCamp",
                skills=["Java"],
                description="Curated free Java learning path.",
                estimated_hours=25,
                value_score=34,
                rating=4.5,
                rating_count=5000,
                study_tip=_study_tip("course", 25),
            ),
        ),
        (
            ("devops", "kubernetes", "docker"),
            ResourceOut(
                kind="course",
                title="kubernetes/kubernetes — learning & tutorials hub",
                url="https://kubernetes.io/docs/tutorials/",
                provider="Kubernetes",
                skills=["Kubernetes"],
                description="Official free Kubernetes tutorials.",
                estimated_hours=16,
                value_score=35,
                rating=4.6,
                rating_count=8000,
                study_tip=_study_tip("course", 16),
            ),
        ),
    ]
    hay = f"{role} {' '.join(skills)}".lower()
    picked: list[ResourceOut] = []
    for keys, resource in catalog:
        if any(k in hay for k in keys):
            tip_skills = _skills_from_query(hay)
            score = compute_value_score(
                rating=resource.rating,
                rating_count=resource.rating_count,
                skill_hits=_skill_hits(tip_skills, hay, resource.title, resource.description),
                learningish=True,
            )
            picked.append(resource.model_copy(update={"value_score": score, "skills": tip_skills or resource.skills}))
    if not picked:
        picked = [catalog[3][1], catalog[0][1]]
    return rank_resources(picked)[:limit]


def fetch_learning_bundle(
    role: str,
    stack_skills: list[str],
    gap_skills: list[str],
    *,
    limit: int = 15,
    blocked_urls: set[str] | None = None,
) -> dict[str, list[ResourceOut]]:
    queries = _queries(role, stack_skills, gap_skills)
    skill_focus = (stack_skills[:3] or gap_skills[:3] or [role])[0]
    blocked = blocked_urls or set()
    primary_limit = max(limit, 15)

    # Books: curated trusted retailers/publishers first; Google Books only as
    # discovery (links rewritten to Goodreads/Amazon/Manning/etc.).
    curated = _trusted_books_for_query(
        role, stack_skills + gap_skills, limit=primary_limit + 2
    )
    discovered = _merge_queries(
        _fetch_google_books,
        queries[:3],
        per_query=4,
        limit=primary_limit + 2,
    )
    books = filter_trusted_resources(
        rank_resources(_dedupe([*curated, *discovered])),
        blocked_urls=blocked,
    )[:primary_limit]
    if not books:
        books = filter_trusted_resources(
            _trusted_books_for_query(role, [skill_focus], limit=primary_limit),
            blocked_urls=blocked,
        )

    youtube = _merge_queries(
        _fetch_youtube_courses, queries[:2], per_query=4, limit=primary_limit
    )
    github_courses = _merge_queries(
        _fetch_github_learning, queries[:3], per_query=4, limit=primary_limit + 4
    )
    algo = _algorithm_practice_links(role, stack_skills + gap_skills)
    rest = filter_trusted_resources(
        rank_resources(_dedupe([*youtube, *github_courses])),
        blocked_urls=blocked,
    )
    # Pin LeetCode / NeetCode at the front when relevant, then fill with other courses.
    algo_f = filter_trusted_resources(algo, blocked_urls=blocked)
    courses = _dedupe([*algo_f, *rest])[:primary_limit]
    if not courses:
        courses = filter_trusted_resources(
            _dedupe(
                [
                    *algo_f,
                    *_fallback_courses(
                        role, stack_skills + gap_skills, limit=primary_limit
                    ),
                ]
            ),
            blocked_urls=blocked,
        )[:primary_limit]

    secondary_limit = 6
    certifications = filter_trusted_resources(
        _merge_queries(
            _fetch_certification_pages,
            [skill_focus, role] + gap_skills[:2],
            per_query=2,
            limit=secondary_limit + 2,
        ),
        blocked_urls=blocked,
    )[:secondary_limit]

    interview_queries = [
        f"{s} interview" for s in (stack_skills[:2] + gap_skills[:2] or [role])
    ]
    interview_questions = filter_trusted_resources(
        _merge_queries(
            _fetch_stack_interview,
            interview_queries[:3],
            per_query=3,
            limit=secondary_limit + 2,
        ),
        blocked_urls=blocked,
    )[:secondary_limit]

    books = _attach_reviews(books[:primary_limit], per_item=5)
    courses = _attach_reviews(courses[:primary_limit], per_item=5)
    certifications = _attach_reviews(certifications[:secondary_limit], per_item=5)
    interview_questions = _attach_reviews(
        interview_questions[:secondary_limit], per_item=5
    )

    return {
        "books": rank_resources(books),
        "courses": rank_resources(courses),
        "certifications": rank_resources(certifications),
        "interview_questions": rank_resources(interview_questions),
    }


def fetch_resources_for_topics(
    topics: list[str],
    role: str,
    *,
    kinds: set[str] | None = None,
    limit_per_topic: int = 3,
) -> list[ResourceOut]:
    kinds = kinds or {"book", "course"}
    out: list[ResourceOut] = []
    for topic in topics:
        q = f"{topic} {role}".strip()
        if "book" in kinds:
            out.extend(
                _trusted_books_for_query(topic, [role], limit=2)
                or _fetch_google_books(q, 2)
            )
        if "course" in kinds:
            yt = _fetch_youtube_courses(q, 2)
            out.extend(yt or _fetch_github_learning(q, 2))
            out.extend(_algorithm_practice_links(role, [topic]))
    return filter_trusted_resources(rank_resources(_dedupe(out)))[
        : limit_per_topic * max(1, len(topics))
    ]
