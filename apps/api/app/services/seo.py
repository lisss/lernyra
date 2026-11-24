from __future__ import annotations

import html
import json
import re
from urllib.parse import quote

from app.services.roles import ROLE_TITLES, requirement_family, requirements_for_role

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_TITLES = set(ROLE_TITLES)

# First keyword of each family in roles._ROLE_REQUIREMENTS.
_PROFILES: dict[str, dict[str, object]] = {
    "python backend": {
        "summary": (
            "A Python developer builds the server side of a product: APIs, data access, "
            "and the jobs that move data around. Teams use the title for backend work "
            "and for smaller groups where one person owns the service."
        ),
        "duties": (
            "Ship and maintain HTTP APIs that other parts of the product call.",
            "Write SQL and change PostgreSQL schemas as features grow.",
            "Run the service in Docker and trace failures after it is deployed.",
            "Read a Python codebase you did not start, and change it without breaking callers.",
        ),
        "focus": (
            "Learn to read and write Python first, then SQL, then how a REST API is put together. "
            "Add Docker once you can run a small service on your own machine."
        ),
        "interview": (
            "Walk through a small API: routes, checks on input, and where the database sits.",
            "Explain a slow query or a timeout, and what you would check first.",
            "Describe a change you made in Python you did not originally write.",
        ),
    },
    "react native": {
        "summary": (
            "A React Native developer ships mobile apps for iOS and Android from one "
            "JavaScript codebase, usually with React and TypeScript."
        ),
        "duties": (
            "Build screens that feel right on a phone, not a stretched website.",
            "Call REST APIs and keep the UI in sync with loading and error states.",
            "Share code across iOS and Android without hiding platform differences.",
            "Fix layout, navigation, and performance issues on a real device.",
        ),
        "focus": (
            "Start with JavaScript and React, then TypeScript, then the mobile pieces: "
            "navigation, device APIs, and how a release reaches a phone."
        ),
        "interview": (
            "Show a screen you built and how data gets from an API into the UI.",
            "Explain a bug that only showed up on one platform.",
            "Say how you would keep a list smooth when it has a lot of rows.",
        ),
    },
    "react": {
        "summary": (
            "Frontend engineers build the part of a product people see in the browser. "
            "Most of these titles expect JavaScript, TypeScript, React, and solid HTML and CSS."
        ),
        "duties": (
            "Turn a design into pages that work with the keyboard and on a small screen.",
            "Fetch data from REST APIs and show loading, empty, and error states.",
            "Keep components understandable as the UI grows.",
            "Fix layout and accessibility issues, not only happy-path clicks.",
        ),
        "focus": (
            "Learn HTML, CSS, and JavaScript until you can build a page without a tutorial, "
            "then React and TypeScript. Next.js matters after those feel ordinary."
        ),
        "interview": (
            "Build or talk through a small React screen with state and an API call.",
            "Explain a CSS bug you tracked down.",
            "Say how you would make a component usable from the keyboard.",
        ),
    },
    "node": {
        "summary": (
            "A Node.js developer builds server applications in JavaScript or TypeScript: "
            "APIs, auth, and the glue between the browser and the database."
        ),
        "duties": (
            "Design REST endpoints and the status codes and payloads they return.",
            "Read and write SQL from Node without blocking the process on slow work.",
            "Share types or contracts with frontend code when the stack is TypeScript.",
            "Package the service with Docker so other people can run it.",
        ),
        "focus": (
            "JavaScript on the server is the core. Add TypeScript, then REST and SQL, "
            "then Docker so you can run what you built the way a team would."
        ),
        "interview": (
            "Sketch an endpoint and what happens when the database is slow.",
            "Explain the difference between a bug in async code and a bug in the query.",
            "Describe how you would structure a small Node service.",
        ),
    },
    "java developer": {
        "summary": (
            "A Java developer builds long-lived backend services, often with Spring, "
            "SQL, and a clear split between API, domain logic, and the database."
        ),
        "duties": (
            "Implement APIs that other teams can rely on for years.",
            "Model data in SQL and keep transactions correct.",
            "Use Spring (or the team's framework) without hiding how requests flow.",
            "Read stack traces and tests well enough to change a large codebase.",
        ),
        "focus": (
            "Learn Java and the basics of objects and tests, then SQL and REST. "
            "Spring is the usual framework once you can explain a request from HTTP to the database."
        ),
        "interview": (
            "Trace a request from the controller to the database and back.",
            "Explain a transaction and what should happen if a step fails.",
            "Talk about a bug you found with a test or a log, not only by clicking.",
        ),
    },
    "golang": {
        "summary": (
            "A Go developer builds small, fast services: HTTP APIs, workers, and tooling. "
            "The usual surroundings are Docker, SQL, and sometimes Kubernetes."
        ),
        "duties": (
            "Write HTTP services with clear error handling and simple concurrency.",
            "Store and query data in SQL.",
            "Ship the binary in a container.",
            "Keep packages small enough that another person can change them.",
        ),
        "focus": (
            "Learn Go's syntax, errors, and goroutines with a real HTTP service, "
            "then SQL and Docker. Kubernetes comes after you can run one service well."
        ),
        "interview": (
            "Explain how a request is handled and where an error returns to the caller.",
            "Describe a concurrency bug, or why a piece of code did not need a goroutine.",
            "Walk through how you would deploy a single Go service.",
        ),
    },
    "full stack": {
        "summary": (
            "A full stack engineer works on the UI and the API behind it. "
            "The usual mix is TypeScript, React, Node.js, and SQL."
        ),
        "duties": (
            "Build a screen and the endpoint it calls.",
            "Model the data in SQL so both sides stay consistent.",
            "Decide what lives in the browser and what must stay on the server.",
            "Ship a small feature across the stack without handing half of it off.",
        ),
        "focus": (
            "Learn JavaScript and SQL before trying to be deep on both React and Node. "
            "Then build one feature that includes the page, the API, and the table."
        ),
        "interview": (
            "Describe a feature from the click in the UI to the row in the database.",
            "Say what you would not put in the browser.",
            "Explain a bug that was on the wrong side of the stack from your first guess.",
        ),
    },
    "backend": {
        "summary": (
            "A backend engineer designs the services behind a product: APIs, data stores, "
            "and the behaviour other teams depend on. Language varies; SQL, REST, and Docker do not."
        ),
        "duties": (
            "Design APIs and the data model they expose.",
            "Keep queries and transactions correct as load and features grow.",
            "Run services in Docker and notice when they fail.",
            "Make tradeoffs in system design that you can explain simply.",
        ),
        "focus": (
            "Pick one language you can write fluently, then spend real time on SQL and API design. "
            "Docker and a cloud provider come after a service works locally."
        ),
        "interview": (
            "Design a small service: data, endpoints, and what happens when a dependency is down.",
            "Explain an index or a query plan in plain language.",
            "Describe a production incident and what you changed afterwards.",
        ),
    },
    "data engineer": {
        "summary": (
            "A data engineer builds pipelines that move and reshape data so other people can trust it. "
            "Python, SQL, and a warehouse or Spark-style processing are the usual core."
        ),
        "duties": (
            "Model tables and write SQL that analysts can reuse.",
            "Build jobs that extract, transform, and load data on a schedule.",
            "Notice broken or late data before a dashboard silently lies.",
            "Keep pipelines deployable, often with Docker and a cloud account.",
        ),
        "focus": (
            "SQL first, then Python for the transforms SQL is bad at. "
            "Add a workflow tool such as Airflow, then Spark or a warehouse, once you have one pipeline that runs twice."
        ),
        "interview": (
            "Walk through a pipeline: source, transform, destination, and how you know it failed.",
            "Write or describe a SQL query with a join and an aggregation.",
            "Explain how you would backfill a day of bad data.",
        ),
    },
    "data scientist": {
        "summary": (
            "Data scientists and analysts use Python and SQL to answer questions with data. "
            "Scientists go further into models; analysts go further into decisions and reporting."
        ),
        "duties": (
            "Write SQL that defines the question, not only the chart.",
            "Clean and analyse data in Python with Pandas.",
            "Explain a result, including what would make it wrong.",
            "Hand a model or a metric to someone who was not in the analysis.",
        ),
        "focus": (
            "SQL and Pandas are the daily tools. Statistics and machine learning come after "
            "you can pull a trustworthy dataset and say what it does not show."
        ),
        "interview": (
            "Take a vague question and say which table and metric you would use.",
            "Explain a result you did not trust, and how you checked it.",
            "Describe a model or analysis in terms a product manager could use.",
        ),
    },
    "machine learning": {
        "summary": (
            "An ML or AI engineer trains, evaluates, and runs models, almost always in Python. "
            "The job is the model plus the data and the service around it, not a notebook that never ships."
        ),
        "duties": (
            "Prepare data and be honest about leakage and bias in the split.",
            "Train and compare models in PyTorch or a similar library.",
            "Measure quality with a metric the product actually cares about.",
            "Package a model so another service can call it.",
        ),
        "focus": (
            "Python and the math you need to read a training loop come first. "
            "Then one framework, PyTorch if you have no reason to pick another, plus SQL so you can build the dataset."
        ),
        "interview": (
            "Explain a model you trained: data, metric, and the baseline it had to beat.",
            "Say how you would tell overfitting from a bad dataset.",
            "Describe how a prediction gets from the model to a user.",
        ),
    },
    "devops": {
        "summary": (
            "DevOps, SRE, and platform engineers keep software deployable and running. "
            "Linux, Docker, Kubernetes, CI/CD, and a cloud account are the common toolkit."
        ),
        "duties": (
            "Build a path from a merge to a running service.",
            "Define infrastructure with Terraform or the team's equivalent.",
            "Page yourself less: alerts that mean something, and runbooks for the rest.",
            "Debug Linux, networking, and containers when a deploy misbehaves.",
        ),
        "focus": (
            "Learn Linux and Docker until you can explain what is running and why. "
            "Then CI/CD, then Kubernetes and Terraform. Cloud console clicking does not replace those."
        ),
        "interview": (
            "Walk through a deploy from commit to production.",
            "Explain a container that will not start, step by step.",
            "Describe an alert you would delete, and one you would keep.",
        ),
    },
    "security": {
        "summary": (
            "A security engineer looks for how a system can be abused and how to close that path. "
            "Linux, networking, and enough Python to automate checks are the usual baseline."
        ),
        "duties": (
            "Review designs and configs for the obvious ways in.",
            "Trace a request across the network and say where trust changes.",
            "Automate a check so it does not depend on someone remembering it.",
            "Explain a risk in language an engineering team can act on.",
        ),
        "focus": (
            "Learn networking and Linux first so the rest is concrete. "
            "Then practice on real apps: auth, input, secrets, and logs. Python is how you scale the boring checks."
        ),
        "interview": (
            "Pick a simple web app and name three ways you would attack it.",
            "Explain a finding you would report, and one you would not.",
            "Say how you would confirm a fix actually closed the issue.",
        ),
    },
    "qa": {
        "summary": (
            "QA and test engineers decide how a team knows the product still works. "
            "That is test design first, then automation in JavaScript or Python and a CI pipeline."
        ),
        "duties": (
            "Find the cases that break a feature, including the ones the ticket forgot.",
            "Automate the checks that should run on every change.",
            "Read API responses and logs well enough to isolate a failure.",
            "Tell the difference between a product bug and a bad test.",
        ),
        "focus": (
            "Learn how to test a feature by hand with intent, then automate those cases. "
            "Git and CI matter so the tests run without you. A language, usually Python or JavaScript, is the tool, not the job."
        ),
        "interview": (
            "Given a feature, list the cases you would test and which you would automate.",
            "Explain a flaky test you fixed or deleted.",
            "Describe how a bug report should be written so someone else can reproduce it.",
        ),
    },
    "ios": {
        "summary": (
            "An iOS developer builds apps in Swift for iPhone and iPad: UI, networking, "
            "and the platform rules Apple actually enforces."
        ),
        "duties": (
            "Build screens that follow iOS patterns people already know.",
            "Call REST APIs and persist what the app needs offline.",
            "Handle lifecycle, permissions, and background limits.",
            "Ship through a build that can be reviewed and released.",
        ),
        "focus": (
            "Swift and UIKit or SwiftUI come first. Build a small app that calls an API "
            "before you collect more frameworks."
        ),
        "interview": (
            "Explain the data flow of a screen you built.",
            "Describe a crash or a memory issue and how you found it.",
            "Say what you would keep on device and what you would fetch again.",
        ),
    },
    "android": {
        "summary": (
            "An Android developer builds apps in Kotlin: screens, navigation, and the "
            "networking behind them, on devices that are not all new phones."
        ),
        "duties": (
            "Build UI that survives rotation, process death, and slow networks.",
            "Call REST APIs and show honest error states.",
            "Keep the app responsive on a modest device.",
            "Structure modules so a second screen does not copy the first one badly.",
        ),
        "focus": (
            "Learn Kotlin, then Android UI and a single networking path. "
            "Ship one app you can install on a device before adding more libraries."
        ),
        "interview": (
            "Walk through a screen's state when the network call fails.",
            "Explain a lifecycle bug.",
            "Describe how you would support a phone that is several years old.",
        ),
    },
    "software engineer": {
        "summary": (
            "Software engineer is the broad title. Hiring teams still expect the same floor: "
            "you can write correct code, use data structures on purpose, talk to an API, and read SQL."
        ),
        "duties": (
            "Take a problem from a short description to code that other people can change.",
            "Choose a simple data structure or algorithm and say why.",
            "Call or build a REST endpoint and store what has to last in SQL.",
            "Review someone else's change and explain your own.",
        ),
        "focus": (
            "Spend time on programming fundamentals and one language you can write without notes. "
            "Then SQL, HTTP, and git as daily tools, not extra topics."
        ),
        "interview": (
            "Solve a small problem out loud and test the edges.",
            "Explain a tradeoff you made in a project.",
            "Read a short piece of code and say what it does and what you would change.",
        ),
    },
}

_SKILL_WHY: dict[str, str] = {
    "Python": "Most of the scripts, services, or analysis for this title are written in Python.",
    "SQL": "You will read and change data with queries, not only with application code.",
    "PostgreSQL": "Teams expect you to design tables and indexes, not only to call an ORM.",
    "REST": "Services talk to each other, and to the UI, with HTTP APIs.",
    "FastAPI": "A common way Python teams expose those APIs.",
    "Docker": "The service has to run somewhere other than your laptop.",
    "System Design": "You should be able to sketch how the pieces fit and where they fail.",
    "Redis": "Used when a database query is the wrong place for a cache or a short-lived value.",
    "AWS": "A lot of this work is deployed on a cloud account, and AWS is the usual one.",
    "React": "The UI is built as components, and React is the library these titles ask for.",
    "TypeScript": "Typed JavaScript is how these teams keep a growing codebase honest.",
    "JavaScript": "The language of the browser and, for several of these titles, the server.",
    "Mobile": "The interface is a phone app, with touch, small screens, and app-store limits.",
    "HTML": "You still need the document underneath the framework.",
    "CSS": "Layout, type, and states are part of the job, not a hand-off.",
    "Next.js": "A common React framework once the app has routing and server needs.",
    "Tailwind CSS": "One widespread way teams write the styles.",
    "Node.js": "JavaScript on the server, usually for APIs.",
    "Java": "The language these services are written in.",
    "Spring": "The framework most Java job ads mean when they say Java.",
    "Go": "The language these services are written in.",
    "Kubernetes": "How teams run many containers once one Docker image is not the whole story.",
    "Apache Spark": "Processing data that is too big for a single script.",
    "Airflow": "Scheduling and watching the jobs that move data.",
    "Kafka": "A stream of events between systems, when a nightly batch is too slow.",
    "Pandas": "The Python library used to clean and reshape tabular data.",
    "Machine Learning": "Building a model is part of the job, not a side topic.",
    "NumPy": "Numerical work in Python sits on NumPy, including a lot of model code.",
    "PyTorch": "The library these teams most often expect for training models.",
    "TensorFlow": "Still common in production stacks and in older code you will have to read.",
    "Linux": "Debugging and deploys happen on Linux, often inside a container.",
    "CI/CD": "Tests and deploys should run on every change, not from someone's memory.",
    "Terraform": "Infrastructure described in files, so it can be reviewed and repeated.",
    "Networking": "You need to say where a request goes and where a trust boundary is.",
    "Testing": "The work is designing checks that catch a broken product.",
    "Swift": "The language iOS apps are written in.",
    "iOS": "Platform APIs, layout, and App Store constraints are the job around the language.",
    "Kotlin": "The language Android apps are written in.",
    "Android": "Platform APIs, device differences, and the app lifecycle sit around Kotlin.",
    "Data Structures": "Interviews and real code both expect you to pick a structure on purpose.",
    "Algorithms": "You should recognise when a naive loop will not survive the input size.",
    "C#": "A .NET title means day-to-day code in C#.",
    ".NET": "The platform around C# for APIs and application structure.",
    "Vue": "The UI framework this title is hired to use.",
    "Angular": "The UI framework this title is hired to use.",
    "Flutter": "Cross-platform UI in Dart, which is the point of this title.",
}


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


def related_role_titles(title: str, limit: int = 6) -> list[str]:
    keys = requirement_family(title)
    if keys is None:
        return []
    others = [
        other
        for other in ROLE_TITLES
        if other != title and requirement_family(other) == keys
    ]
    # Base titles first so the main guides, not every seniority variant, get the links.
    others.sort(key=lambda name: ("senior" in name.lower() or name.lower().startswith("mid"), name.lower()))
    return others[:limit]


def _paired_title(title: str) -> str | None:
    for prefix in ("Senior ", "Mid-level "):
        if title.startswith(prefix):
            base = title[len(prefix) :]
            if base in _TITLES:
                return base
    for prefix in ("Senior ", "Mid-level "):
        other = f"{prefix}{title}"
        if other in _TITLES:
            return other
    return None


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


def _profile(title: str) -> dict[str, object] | None:
    keys = requirement_family(title)
    if not keys:
        return None
    return _PROFILES.get(keys[0])


def _as_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    return ()


def _weight_label(pct: float) -> str:
    if pct >= 85:
        return "core skill"
    if pct >= 65:
        return "commonly required"
    return "useful alongside the core skills"


def _english_list(items: list[str]) -> str:
    if not items:
        return "the core toolkit for the title"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _clip(text: str, limit: int = 155) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:")
    return cut + "."


def _meta_description(title: str, skills: list[str]) -> str:
    listed = _english_list(skills[:3])
    return _clip(
        f"Typical {title} skills: {listed}. "
        "What the job involves, which skills come first, and how to plan study."
    )


def _fallback_profile(title: str) -> dict[str, object]:
    return {
        "summary": (
            f"A {title} is hired for the mix of skills below. "
            "The labels say how central each skill usually is for this title."
        ),
        "duties": (
            "Deliver work that depends on the skills listed for this title.",
            "Explain your approach when the requirements are incomplete.",
            "Change an existing codebase without treating every task as a rewrite.",
        ),
        "focus": (
            f"Learn the core skills for a {title} before the optional ones. "
            "Use a project, not only a course: something you can explain line by line."
        ),
        "interview": (
            "Be ready to explain the top skills with an example from a project.",
            "Expect more depth on the first two or three skills than on the rest of the list.",
        ),
    }


def _json_ld(data: object) -> str:
    return json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")


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


def build_llms_txt(site: str) -> str:
    site = site.rstrip("/")
    lines = [
        "# Lernyra",
        "",
        "> Lernyra lists the skills a job title usually requires, compares them with your CV, and suggests books, courses, and interview prep.",
        "",
        "Lernyra does not list job openings. The interactive planner is the homepage. Each role guide is a separate public page for one title.",
        "",
        "## Pages",
        f"- [Planner]({site}/): compare a role with your skills or CV and get a study plan",
        f"- [Role guides]({site}/roles): every title, grouped alphabetically",
        "",
        "## Role guides",
    ]
    for slug, title in sitemap_role_slugs():
        skills = [skill for skill, _pct in requirements_for_role(title)[:4]]
        detail = _english_list(skills)
        lines.append(f"- [{title}]({site}/roles/{slug}): typical skills include {detail}")
    lines.append("")
    return "\n".join(lines)


def _page_style() -> str:
    return """
    :root { color-scheme: light; --ink:#1c2422; --muted:#5f6d69; --brand:#1f4f4a; --line:rgba(28,36,34,.12); --bg:#f6f8f7; --card:#eef6f3; }
    body { margin:0; font-family:"Plus Jakarta Sans",system-ui,sans-serif; color:var(--ink); background:var(--bg); line-height:1.55; }
    main { max-width:42rem; margin:0 auto; padding:2.5rem 1.25rem 4rem; }
    a { color:#1a5f9e; }
    h1 { font-size:clamp(1.5rem,4vw,2rem); letter-spacing:-.03em; color:var(--brand); margin:0 0 .75rem; }
    h2 { font-size:1.25rem; margin:1.75rem 0 .5rem; }
    h3 { font-size:1.05rem; margin:1.1rem 0 .25rem; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:.5rem; padding:1.25rem 1.35rem; margin:1.5rem 0; }
    .cta { display:inline-block; margin-top:1rem; padding:.7rem 1.1rem; background:var(--brand); color:#fff; text-decoration:none; border-radius:.375rem; font-weight:600; }
    ul, ol { padding-left:1.15rem; }
    li { margin:.35rem 0; }
    .muted { color:var(--muted); }
    footer { margin-top:2.5rem; font-size:.875rem; color:var(--muted); }
"""


def _head(site: str, page_title: str, description: str, canonical: str, json_ld: str) -> str:
    esc_site = html.escape(site)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{page_title}</title>
  <meta name="description" content="{description}" />
  <link rel="canonical" href="{canonical}" />
  <meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Lernyra" />
  <meta property="og:locale" content="en_US" />
  <meta property="og:title" content="{page_title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:image" content="{esc_site}/og.png" />
  <meta property="og:image:type" content="image/png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content="Lernyra — role requirements and learning paths" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{page_title}" />
  <meta name="twitter:description" content="{description}" />
  <meta name="twitter:image" content="{esc_site}/og.png" />
  <meta name="twitter:image:alt" content="Lernyra — role requirements and learning paths" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <script type="application/ld+json">{json_ld}</script>
  <style>{_page_style()}</style>
</head>
"""


def build_role_page_html(site: str, title: str) -> str:
    site = site.rstrip("/")
    slug = role_slug(title)
    reqs = requirements_for_role(title)
    profile = _profile(title) or _fallback_profile(title)
    summary = str(profile["summary"])
    duties = _as_tuple(profile["duties"])
    focus = str(profile["focus"])
    interview = _as_tuple(profile["interview"])
    esc_title = html.escape(title)
    page_title = html.escape(f"{title} skills & requirements | Lernyra")
    skill_names = [skill for skill, _pct in reqs[:8]] or [title]
    description = html.escape(_meta_description(title, skill_names))
    canonical = html.escape(f"{site}/roles/{slug}")
    app_link = html.escape(f"{site}/?q={quote(title)}")
    note = html.escape(_seniority_note(title))

    skill_items = []
    for skill, pct in reqs[:12]:
        why = _SKILL_WHY.get(skill, "")
        why_html = f" {html.escape(why)}" if why else ""
        skill_items.append(
            f"      <li><strong>{html.escape(skill)}</strong>"
            f" <span class=\"muted\">— {_weight_label(pct)}.</span>{why_html}</li>"
        )
    if not skill_items:
        skill_items.append("      <li>Typical skills for this role appear in the planner.</li>")

    duty_html = "\n".join(f"      <li>{html.escape(item)}</li>" for item in duties)
    interview_html = "\n".join(f"      <li>{html.escape(item)}</li>" for item in interview)
    learn_items = "\n".join(
        f"      <li><strong>{html.escape(skill)}</strong></li>" for skill in skill_names[:5]
    )

    pair = _paired_title(title)
    pair_html = ""
    if pair:
        pair_html = (
            f'<p>Related guide: <a href="{html.escape(site)}/roles/{role_slug(pair)}">'
            f"{html.escape(pair)} skills and requirements</a>.</p>"
        )

    related = [name for name in related_role_titles(title) if name != pair]
    related_html = ""
    if related:
        links = "\n".join(
            f'        <li><a href="{html.escape(site)}/roles/{role_slug(other)}">'
            f"{html.escape(other)} skills and requirements</a></li>"
            for other in related
        )
        related_html = f"""
    <div class="card">
      <h2>Related role guides</h2>
      <ul>
{links}
      </ul>
    </div>"""

    skill_list = _english_list(skill_names[:5])
    faq = [
        (
            f"What skills does a {title} need?",
            f"The skills that usually matter for a {title} are {skill_list}. "
            "Core skills are the ones to learn before the rest.",
        ),
        (
            f"How do I learn {title} skills?",
            f"{focus} Then compare the list with your CV on Lernyra so you study the gaps, not the skills you already have.",
        ),
        (
            f"What does a {title} do day to day?",
            summary,
        ),
    ]
    page_url = f"{site}/roles/{slug}"
    graph: list[dict[str, object]] = [
        {
            "@type": "WebPage",
            "@id": page_url,
            "name": f"{title} skills and requirements",
            "description": _meta_description(title, skill_names),
            "url": page_url,
            "inLanguage": "en",
            "isPartOf": {"@type": "WebSite", "name": "Lernyra", "url": f"{site}/"},
            "breadcrumb": {"@id": f"{page_url}#breadcrumb"},
            "about": {"@id": f"{page_url}#occupation"},
            "primaryImageOfPage": {
                "@type": "ImageObject",
                "url": f"{site}/og.png",
            },
        },
        {
            "@type": "Occupation",
            "@id": f"{page_url}#occupation",
            "name": title,
            "description": summary,
            "skills": [
                {"@type": "DefinedTerm", "name": skill, "description": _SKILL_WHY.get(skill, "")}
                for skill in skill_names
                if _SKILL_WHY.get(skill)
            ]
            or skill_names,
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
    ]
    if pair:
        graph[0]["relatedLink"] = f"{site}/roles/{role_slug(pair)}"

    faq_html = "\n".join(
        f"      <h3>{html.escape(question)}</h3><p>{html.escape(answer)}</p>"
        for question, answer in faq
    )
    ld_raw = _json_ld({"@context": "https://schema.org", "@graph": graph})

    return f"""{_head(site, page_title, description, canonical, ld_raw)}<body>
  <main>
    <p class="muted">
      <a href="{html.escape(site)}/">Lernyra</a>
      · <a href="{html.escape(site)}/roles">Role guides</a>
      · {esc_title}
    </p>
    <h1>{esc_title}: skills and requirements</h1>
    <p>{html.escape(summary)}</p>
    <p>{note}</p>
    {pair_html}
    <div class="card">
      <h2>Typical requirements</h2>
      <p class="muted">Ordered by how central the skill usually is for this title.</p>
      <ul>
{chr(10).join(skill_items)}
      </ul>
      <a class="cta" href="{app_link}">Compare your CV with {esc_title} skills</a>
    </div>
    <h2>What the work looks like</h2>
    <ul>
{duty_html}
    </ul>
    <h2>What to learn first</h2>
    <p>{html.escape(focus)}</p>
    <ol>
{learn_items}
    </ol>
    <h2>What interviews tend to ask</h2>
    <ul>
{interview_html}
    </ul>
    <h2>Questions people ask</h2>
{faq_html}
{related_html}
    <footer>
      <a href="{html.escape(site)}/roles">All role guides</a>
      · <a href="{html.escape(site)}/">Plan learning for a role</a>
      · <a href="{html.escape(site)}/sitemap.xml">Sitemap</a>
    </footer>
  </main>
</body>
</html>
"""


_START_HERE = (
    "Software Engineer",
    "Python Developer",
    "Frontend Engineer",
    "Backend Engineer",
    "Data Engineer",
    "Data Scientist",
    "DevOps Engineer",
    "Machine Learning Engineer",
    "Security Engineer",
    "QA Engineer",
)


def build_roles_index_html(site: str) -> str:
    site = site.rstrip("/")
    groups: dict[str, list[tuple[str, str]]] = {}
    for slug, title in sitemap_role_slugs():
        letter = title[0].upper() if title[:1].isalpha() else "#"
        groups.setdefault(letter, []).append((slug, title))

    sections = []
    for letter in sorted(groups):
        items = "\n".join(
            f'        <li><a href="{html.escape(site)}/roles/{slug}">{html.escape(title)} skills and requirements</a></li>'
            for slug, title in groups[letter]
        )
        anchor = letter.lower() if letter.isalpha() else "other"
        sections.append(
            f'    <h2 id="{html.escape(anchor)}">{html.escape(letter)}</h2>\n    <ul>\n{items}\n    </ul>'
        )
    body = "\n".join(sections)
    count = sum(len(v) for v in groups.values())
    description = html.escape(
        _clip(
            f"Browse {count} Lernyra role guides. Each page lists the skills that job title usually requires and what to learn first.",
            160,
        )
    )
    page_title = html.escape("Role guides — skills by job title | Lernyra")
    start_links = "\n".join(
        f'        <li><a href="{html.escape(site)}/roles/{role_slug(title)}">{html.escape(title)} skills and requirements</a></li>'
        for title in _START_HERE
        if title in _TITLES
    )
    json_ld = _json_ld(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": "Lernyra role guides",
                    "description": f"{count} job-title guides with typical skills and what to learn first.",
                    "url": f"{site}/roles",
                    "inLanguage": "en",
                    "isPartOf": {"@type": "WebSite", "name": "Lernyra", "url": f"{site}/"},
                    "breadcrumb": {"@id": f"{site}/roles#breadcrumb"},
                },
                {
                    "@type": "BreadcrumbList",
                    "@id": f"{site}/roles#breadcrumb",
                    "itemListElement": [
                        {"@type": "ListItem", "position": 1, "name": "Lernyra", "item": f"{site}/"},
                        {"@type": "ListItem", "position": 2, "name": "Role guides", "item": f"{site}/roles"},
                    ],
                },
            ],
        }
    )
    return f"""{_head(site, page_title, description, html.escape(f"{site}/roles"), json_ld)}<body>
  <main>
    <p class="muted"><a href="{html.escape(site)}/">Lernyra</a> · Role guides</p>
    <h1>Role guides: skills by job title</h1>
    <p>
      Each guide lists the skills a title usually requires, what the work looks like,
      and a sensible order to learn them. Open the planner when you want that list
      compared with your CV.
    </p>
    <h2>Start here</h2>
    <ul>
{start_links}
    </ul>
{body}
    <footer>
      <a href="{html.escape(site)}/">Plan learning for a role</a>
      · <a href="{html.escape(site)}/sitemap.xml">Sitemap</a>
    </footer>
  </main>
</body>
</html>
"""
