from __future__ import annotations

from app.services.jobs import seniority_rank
from app.services.skills import extract_skills

ROLE_TITLES: list[str] = [
    "Software Engineer",
    "Mid-level Software Engineer",
    "Senior Software Engineer",
    "Software Developer",
    "Senior Software Developer",
    "Application Developer",
    "Full Stack Engineer",
    "Senior Full Stack Engineer",
    "Full Stack Developer",
    "Senior Full Stack Developer",
    "Frontend Engineer",
    "Senior Frontend Engineer",
    "Frontend Developer",
    "Senior Frontend Developer",
    "React Engineer",
    "Senior React Engineer",
    "React Developer",
    "Senior React Developer",
    "React Native Developer",
    "Senior React Native Developer",
    "Vue.js Developer",
    "Angular Developer",
    "UI Engineer",
    "Web Developer",
    "Backend Engineer",
    "Senior Backend Engineer",
    "Backend Developer",
    "Senior Backend Developer",
    "Python Developer",
    "Senior Python Developer",
    "Python Backend Engineer",
    "Java Developer",
    "Senior Java Developer",
    "Node.js Developer",
    "Senior Node.js Developer",
    "Go Developer",
    "Senior Go Developer",
    "API Engineer",
    ".NET Developer",
    "Senior .NET Developer",
    "Mobile Developer",
    "Senior Mobile Developer",
    "iOS Developer",
    "Senior iOS Developer",
    "Android Developer",
    "Senior Android Developer",
    "Flutter Developer",
    "Data Engineer",
    "Senior Data Engineer",
    "Data Scientist",
    "Senior Data Scientist",
    "Data Analyst",
    "Senior Data Analyst",
    "ML Engineer",
    "Machine Learning Engineer",
    "Senior Machine Learning Engineer",
    "AI Engineer",
    "Senior AI Engineer",
    "Analytics Engineer",
    "DevOps Engineer",
    "Senior DevOps Engineer",
    "SRE",
    "Site Reliability Engineer",
    "Senior Site Reliability Engineer",
    "Platform Engineer",
    "Senior Platform Engineer",
    "Cloud Engineer",
    "Senior Cloud Engineer",
    "Infrastructure Engineer",
    "Security Engineer",
    "Senior Security Engineer",
    "Cybersecurity Engineer",
    "QA Engineer",
    "Senior QA Engineer",
    "Quality Assurance Engineer",
    "Test Engineer",
    "Automation Engineer",
    "Product Engineer",
    "Senior Product Engineer",
    "Solutions Engineer",
    "Support Engineer",
    # Leadership (kept but ranked lower via seniority_rank)
    "Tech Lead",
    "Engineering Manager",
    "Staff Software Engineer",
    "Principal Engineer",
]


def suggest_role_titles(q: str = "", limit: int = 12) -> list[str]:
    needle = q.strip().lower()
    limit = max(1, min(limit, 30))

    if not needle:
        defaults = [
            "Software Engineer",
            "Senior Software Engineer",
            "Frontend Engineer",
            "Senior Frontend Engineer",
            "Backend Engineer",
            "Senior Backend Engineer",
            "Full Stack Engineer",
            "Python Developer",
            "React Developer",
            "Data Engineer",
            "DevOps Engineer",
            "ML Engineer",
        ]
        return defaults[:limit]

    starts: list[str] = []
    contains: list[str] = []
    for title in ROLE_TITLES:
        lower = title.lower()
        if lower.startswith(needle):
            starts.append(title)
        elif needle in lower:
            contains.append(title)

    starts.sort(key=lambda t: (seniority_rank(t), t.lower()))
    contains.sort(key=lambda t: (seniority_rank(t), t.lower()))

    seen: set[str] = set()
    results: list[str] = []
    for title in starts + contains:
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(title)
        if len(results) >= limit:
            break
    return results


# Typical requirements by role family. Values are importance 0–100 for the UI.
_ROLE_REQUIREMENTS: list[tuple[tuple[str, ...], list[tuple[str, float]]]] = [
    (
        ("python backend", "python developer", "python engineer"),
        [
            ("Python", 100),
            ("SQL", 90),
            ("PostgreSQL", 85),
            ("REST", 85),
            ("FastAPI", 80),
            ("Docker", 75),
            ("Git", 70),
            ("System Design", 65),
            ("Redis", 55),
            ("AWS", 50),
        ],
    ),
    (
        ("react native",),
        [
            ("React", 100),
            ("TypeScript", 90),
            ("JavaScript", 85),
            ("Mobile", 80),
            ("Git", 70),
            ("REST", 65),
        ],
    ),
    (
        ("react", "frontend", "front-end", "ui engineer", "web developer"),
        [
            ("JavaScript", 95),
            ("TypeScript", 90),
            ("React", 95),
            ("HTML", 80),
            ("CSS", 80),
            ("Git", 70),
            ("REST", 65),
            ("Next.js", 55),
            ("Tailwind CSS", 45),
        ],
    ),
    (
        ("node", "node.js"),
        [
            ("Node.js", 100),
            ("JavaScript", 90),
            ("TypeScript", 85),
            ("REST", 80),
            ("SQL", 70),
            ("Git", 70),
            ("Docker", 55),
        ],
    ),
    (
        ("java developer", "java engineer", "spring"),
        [
            ("Java", 100),
            ("Spring", 85),
            ("SQL", 80),
            ("REST", 75),
            ("Git", 70),
            ("Docker", 55),
            ("System Design", 50),
        ],
    ),
    (
        ("golang", " go developer", " go engineer", "go developer", "go engineer"),
        [
            ("Go", 100),
            ("REST", 80),
            ("Docker", 75),
            ("Kubernetes", 60),
            ("SQL", 60),
            ("Git", 70),
            ("System Design", 55),
        ],
    ),
    (
        ("full stack", "fullstack"),
        [
            ("JavaScript", 90),
            ("TypeScript", 85),
            ("React", 80),
            ("Node.js", 75),
            ("SQL", 70),
            ("REST", 70),
            ("Git", 70),
            ("Docker", 50),
        ],
    ),
    (
        ("backend", "api engineer"),
        [
            ("SQL", 90),
            ("REST", 90),
            ("Docker", 75),
            ("Git", 70),
            ("System Design", 70),
            ("PostgreSQL", 65),
            ("Redis", 50),
            ("AWS", 50),
        ],
    ),
    (
        ("data engineer",),
        [
            ("Python", 90),
            ("SQL", 95),
            ("Apache Spark", 70),
            ("Airflow", 65),
            ("AWS", 60),
            ("Kafka", 55),
            ("Docker", 50),
            ("Git", 60),
        ],
    ),
    (
        ("data scientist", "data analyst", "analytics engineer"),
        [
            ("Python", 90),
            ("SQL", 95),
            ("Pandas", 80),
            ("Machine Learning", 70),
            ("NumPy", 60),
            ("Git", 50),
        ],
    ),
    (
        ("machine learning", "ml engineer", "ai engineer"),
        [
            ("Python", 100),
            ("Machine Learning", 95),
            ("PyTorch", 75),
            ("TensorFlow", 60),
            ("SQL", 55),
            ("Docker", 50),
            ("AWS", 50),
            ("Git", 60),
        ],
    ),
    (
        ("devops", "sre", "site reliability", "platform engineer", "cloud engineer", "infrastructure"),
        [
            ("Linux", 90),
            ("Docker", 90),
            ("Kubernetes", 85),
            ("CI/CD", 85),
            ("AWS", 80),
            ("Terraform", 75),
            ("Python", 55),
            ("Git", 70),
            ("System Design", 60),
        ],
    ),
    (
        ("security", "cybersecurity"),
        [
            ("Linux", 80),
            ("Networking", 75),
            ("AWS", 60),
            ("Python", 55),
            ("Git", 50),
            ("System Design", 45),
        ],
    ),
    (
        ("qa", "quality assurance", "test engineer", "automation engineer"),
        [
            ("Testing", 90),
            ("Git", 70),
            ("CI/CD", 65),
            ("JavaScript", 50),
            ("Python", 50),
            ("REST", 55),
        ],
    ),
    (
        ("ios", "swift"),
        [
            ("Swift", 100),
            ("iOS", 95),
            ("Git", 70),
            ("REST", 60),
        ],
    ),
    (
        ("android", "kotlin"),
        [
            ("Kotlin", 100),
            ("Android", 95),
            ("Git", 70),
            ("REST", 60),
        ],
    ),
    (
        ("software engineer", "software developer", "application developer", "product engineer"),
        [
            ("Git", 80),
            ("Data Structures", 75),
            ("Algorithms", 75),
            ("SQL", 65),
            ("REST", 65),
            ("System Design", 55),
            ("Communication", 50),
        ],
    ),
]


# Soft / ubiquitous skills CVs rarely lead with — drop from Role requirements.
_MINOR_REQUIREMENTS = frozenset(
    {
        "Git",
        "GitHub",
        "Communication",
        "Agile",
        "Scrum",
        "Jira",
        "Problem Solving",
    }
)


def requirement_family(role: str) -> tuple[str, ...] | None:
    """Keyword tuple of the first matching role family, or None."""
    needle = (role or "").strip().lower()
    if not needle:
        return None
    for keys, _skills in _ROLE_REQUIREMENTS:
        if any(k in needle for k in keys):
            return keys
    return None


def requirements_for_role(role: str) -> list[tuple[str, float]]:
    """
    Return (skill, importance%) for a position title.
    No job-board matching — curated requirements for the role family.
    """
    needle = (role or "").strip().lower()
    if not needle:
        return []

    family = requirement_family(role)
    matched: list[tuple[str, float]] = []
    if family is not None:
        for keys, skills in _ROLE_REQUIREMENTS:
            if keys == family:
                matched = list(skills)
                break

    # Merge skills implied by the title wording (e.g. "Python" in the name)
    titled = extract_skills(role)
    by_name = {s: pct for s, pct in matched}
    for skill in titled:
        by_name[skill] = max(by_name.get(skill, 0), 100.0)

    by_name = {
        skill: pct
        for skill, pct in by_name.items()
        if skill not in _MINOR_REQUIREMENTS
    }

    if not by_name:
        by_name = {
            "Data Structures": 70,
            "Algorithms": 65,
            "System Design": 55,
            "SQL": 50,
        }

    ordered = sorted(by_name.items(), key=lambda x: (-x[1], x[0]))
    return [(skill, float(pct)) for skill, pct in ordered]
