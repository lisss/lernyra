from __future__ import annotations

import html
import json
import re

from app.services.roles import ROLE_TITLES, requirements_for_role

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def role_slug(title: str) -> str:
    slug = _SLUG_RE.sub("-", title.strip().lower()).strip("-")
    return slug or "role"


def title_from_slug(slug: str) -> str | None:
    needle = slug.strip().lower().strip("-")
    if not needle:
        return None
    for title in ROLE_TITLES:
        if role_slug(title) == needle:
            return title
    soft = needle.replace("-", " ")
    for title in ROLE_TITLES:
        if title.lower() == soft:
            return title
    return None


def sitemap_role_slugs() -> list[tuple[str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for title in ROLE_TITLES:
        slug = role_slug(title)
        if slug in seen:
            continue
        seen.add(slug)
        out.append((slug, title))
    return out


def build_robots_txt(site: str) -> str:
    site = site.rstrip("/")
    # /learning-list is crawlable on purpose so Google can see its noindex tag.
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "\n"
        f"Sitemap: {site}/sitemap.xml\n"
    )


def _skill_signature(title: str) -> tuple[str, ...]:
    return tuple(skill for skill, _pct in requirements_for_role(title)[:8])


def related_role_titles(title: str, limit: int = 6) -> list[str]:
    signature = _skill_signature(title)
    same: list[str] = []
    for other in ROLE_TITLES:
        if other == title:
            continue
        if _skill_signature(other) == signature:
            same.append(other)
    return same[:limit]


def _seniority_note(title: str) -> str:
    low = title.lower()
    if low.startswith("senior ") or " senior " in f" {low} ":
        return (
            "A senior title usually means you already ship without a checklist: "
            "you pick the design, review other people's work, and can explain tradeoffs."
        )
    if any(word in low for word in ("staff", "principal")):
        return (
            "Staff and principal titles widen the scope past one team. "
            "The skills below are the technical floor; the job adds direction across several projects."
        )
    if "manager" in low or low.startswith("tech lead"):
        return (
            "This title mixes the technical skills below with leading people: "
            "planning work, unblocking others, and keeping a standard."
        )
    if low.startswith("mid-level ") or low.startswith("mid "):
        return (
            "Mid-level means you can take a task from spec to production with light review, "
            "using the skills below without someone pairing the whole way."
        )
    return (
        "Treat the list below as the usual baseline for this title. "
        "Seniority changes how deep each skill needs to go, not the names."
    )


def build_sitemap_xml(site: str) -> str:
    site = site.rstrip("/")
    urls = [
        ("/", "1.0", "weekly"),
        ("/roles", "0.9", "weekly"),
    ]
    for slug, _title in sitemap_role_slugs():
        urls.append((f"/roles/{slug}", "0.7", "monthly"))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, priority, freq in urls:
        parts.append("  <url>")
        parts.append(f"    <loc>{html.escape(site + path)}</loc>")
        parts.append(f"    <changefreq>{freq}</changefreq>")
        parts.append(f"    <priority>{priority}</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    return "\n".join(parts) + "\n"


def build_role_page_html(site: str, title: str) -> str:
    site = site.rstrip("/")
    slug = role_slug(title)
    reqs = requirements_for_role(title)
    esc_title = html.escape(title)
    page_title = html.escape(f"{title} skills & learning path | Lernyra")
    description = html.escape(
        f"See typical {title} role requirements, ranked skills, and a study plan "
        f"with books, courses, and interview prep on Lernyra."
    )
    canonical = html.escape(f"{site}/roles/{slug}")
    app_link = html.escape(f"{site}/?q={title}")

    skill_items = "\n".join(
        f"      <li><strong>{html.escape(skill)}</strong>"
        f" — importance {int(pct)}%</li>"
        for skill, pct in reqs[:15]
    )
    if not skill_items:
        skill_items = "      <li>Typical skills for this role will appear after you open the planner.</li>"

    skill_names = [s for s, _ in reqs[:8]] or [title]
    skill_list = ", ".join(skill_names[:-1]) + (
        f", and {skill_names[-1]}" if len(skill_names) > 1 else skill_names[0]
    )
    note = html.escape(_seniority_note(title))
    related = related_role_titles(title)
    related_html = ""
    if related:
        links = "\n".join(
            f'        <li><a href="{html.escape(site)}/roles/{role_slug(other)}">'
            f"{html.escape(other)}</a></li>"
            for other in related
        )
        related_html = f"""
    <div class="card">
      <h2>Related role guides</h2>
      <ul>
{links}
      </ul>
    </div>"""

    page_url = f"{site}/roles/{slug}"
    faq = [
        (
            f"What skills does a {title} need?",
            f"The skills that usually matter for a {title} are {skill_list}.",
        ),
        (
            f"How do I learn {title} skills?",
            f"Compare {skill_list} with your CV on Lernyra, then follow the books, courses, and interview prep it lines up for the gaps.",
        ),
    ]
    json_ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "name": f"{title} learning path",
                "description": (
                    f"Typical requirements and learning resources for a {title} role."
                ),
                "url": page_url,
                "isPartOf": {"@type": "WebSite", "name": "Lernyra", "url": f"{site}/"},
                "breadcrumb": {"@id": f"{page_url}#breadcrumb"},
                "about": {
                    "@type": "Occupation",
                    "name": title,
                    "skills": ", ".join(skill_names),
                },
            },
            {
                "@type": "BreadcrumbList",
                "@id": f"{page_url}#breadcrumb",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Lernyra", "item": f"{site}/"},
                    {"@type": "ListItem", "position": 2, "name": "Role guides", "item": f"{site}/roles"},
                    {"@type": "ListItem", "position": 3, "name": title, "item": page_url},
                ],
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": question,
                        "acceptedAnswer": {"@type": "Answer", "text": answer},
                    }
                    for question, answer in faq
                ],
            },
            {
                "@type": "ItemList",
                "name": f"{title} skills",
                "itemListElement": [
                    {"@type": "ListItem", "position": i, "name": skill}
                    for i, skill in enumerate(skill_names, start=1)
                ],
            },
        ],
    }
    ld_raw = json.dumps(json_ld, ensure_ascii=True)
    faq_html = "\n".join(
        f"      <h3>{html.escape(question)}</h3><p>{html.escape(answer)}</p>"
        for question, answer in faq
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{page_title}</title>
  <meta name="description" content="{description}" />
  <link rel="canonical" href="{canonical}" />
  <meta name="robots" content="index,follow,max-image-preview:large" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Lernyra" />
  <meta property="og:title" content="{page_title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:image" content="{html.escape(site)}/og.svg" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content="Lernyra" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{page_title}" />
  <meta name="twitter:description" content="{description}" />
  <meta name="twitter:image" content="{html.escape(site)}/og.svg" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <script type="application/ld+json">{ld_raw}</script>
  <style>
    :root {{ color-scheme: light; --ink:#1c2422; --muted:#5f6d69; --brand:#1f4f4a; --line:rgba(28,36,34,.12); --bg:#f6f8f7; --card:#eef6f3; }}
    body {{ margin:0; font-family:"Plus Jakarta Sans",system-ui,sans-serif; color:var(--ink); background:var(--bg); line-height:1.55; }}
    main {{ max-width:42rem; margin:0 auto; padding:2.5rem 1.25rem 4rem; }}
    a {{ color:var(--brand); }}
    h1 {{ font-size:clamp(1.5rem,4vw,2rem); letter-spacing:-.03em; color:var(--brand); margin:0 0 .75rem; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:.5rem; padding:1.25rem 1.35rem; margin:1.5rem 0; }}
    .cta {{ display:inline-block; margin-top:1rem; padding:.7rem 1.1rem; background:var(--brand); color:#fff; text-decoration:none; border-radius:.375rem; font-weight:600; }}
    ul {{ padding-left:1.15rem; }}
    li {{ margin:.35rem 0; }}
    .muted {{ color:var(--muted); }}
    footer {{ margin-top:2.5rem; font-size:.875rem; color:var(--muted); }}
  </style>
</head>
<body>
  <main>
    <p class="muted">
      <a href="{html.escape(site)}/">Lernyra</a>
      · <a href="{html.escape(site)}/roles">Role guides</a>
      · {esc_title}
    </p>
    <h1>{esc_title}: skills &amp; learning path</h1>
    <p>
      Lernyra maps what a <strong>{esc_title}</strong> role typically needs,
      then helps you plan books, courses, certifications, and interview prep
      against your own skills or CV.
    </p>
    <p>{note}</p>
    <div class="card">
      <h2>Typical requirements</h2>
      <p class="muted">Ranked by how often they show up for this kind of role.</p>
      <ul>
{skill_items}
      </ul>
      <a class="cta" href="{app_link}">Plan your learning for {esc_title}</a>
    </div>
    <h2>Questions people ask</h2>
{faq_html}
{related_html}
    <footer>
      <a href="{html.escape(site)}/roles">All role guides</a>
      · <a href="{html.escape(site)}/sitemap.xml">Sitemap</a>
    </footer>
  </main>
</body>
</html>
"""


def build_roles_index_html(site: str) -> str:
    site = site.rstrip("/")
    groups: dict[str, list[tuple[str, str]]] = {}
    for slug, title in sitemap_role_slugs():
        letter = title[0].upper() if title[:1].isalpha() else "#"
        groups.setdefault(letter, []).append((slug, title))

    sections = []
    for letter in sorted(groups):
        items = "\n".join(
            f'        <li><a href="{html.escape(site)}/roles/{slug}">{html.escape(title)}</a></li>'
            for slug, title in groups[letter]
        )
        sections.append(f"    <h2>{html.escape(letter)}</h2>\n    <ul>\n{items}\n    </ul>")
    body = "\n".join(sections)
    count = sum(len(v) for v in groups.values())
    description = html.escape(
        f"Browse {count} Lernyra role guides: typical skills for each job title, then a plan for books, courses, and interview prep."
    )
    page_title = html.escape("Role guides — skills by job title | Lernyra")
    json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "Lernyra role guides",
            "description": f"{count} job-title guides with typical skills and a learning plan.",
            "url": f"{site}/roles",
            "isPartOf": {"@type": "WebSite", "name": "Lernyra", "url": f"{site}/"},
        },
        ensure_ascii=True,
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{page_title}</title>
  <meta name="description" content="{description}" />
  <link rel="canonical" href="{html.escape(site)}/roles" />
  <meta name="robots" content="index,follow" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Lernyra" />
  <meta property="og:title" content="{page_title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="{html.escape(site)}/roles" />
  <meta property="og:image" content="{html.escape(site)}/og.svg" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{page_title}" />
  <meta name="twitter:description" content="{description}" />
  <meta name="twitter:image" content="{html.escape(site)}/og.svg" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <script type="application/ld+json">{json_ld}</script>
  <style>
    :root {{ color-scheme: light; --ink:#1c2422; --muted:#5f6d69; --brand:#1f4f4a; --bg:#f6f8f7; }}
    body {{ margin:0; font-family:"Plus Jakarta Sans",system-ui,sans-serif; color:var(--ink); background:var(--bg); line-height:1.55; }}
    main {{ max-width:42rem; margin:0 auto; padding:2.5rem 1.25rem 4rem; }}
    a {{ color:var(--brand); }}
    h1 {{ font-size:clamp(1.5rem,4vw,2rem); letter-spacing:-.03em; color:var(--brand); margin:0 0 .75rem; }}
    ul {{ padding-left:1.15rem; }}
    li {{ margin:.3rem 0; }}
    .muted {{ color:var(--muted); }}
  </style>
</head>
<body>
  <main>
    <p class="muted"><a href="{html.escape(site)}/">Lernyra</a> · Role guides</p>
    <h1>Role guides</h1>
    <p>{description}</p>
{body}
  </main>
</body>
</html>
"""
