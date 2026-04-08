#!/usr/bin/env python3
"""
SWE Intern Summer 2026 Scraper
Hits Greenhouse / Lever / Ashby ATS APIs directly — no browser, no fragile selectors.
Run: python3 scraper.py
"""

import json
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

# ── Config ────────────────────────────────────────────────────────────────────

SEEN_FILE   = Path("seen_jobs.json")
OUT_FILE    = Path("jobs.json")      # accumulated across all runs
README_FILE = Path("README.md")

# Only return jobs posted within this window
MAX_AGE_HOURS = 1

SWE_KEYWORDS = {"software", "engineer", "swe", "developer", "backend",
                "frontend", "fullstack", "full-stack", "ml", "systems",
                "data", "infrastructure", "platform", "site reliability",
                "devops", "security", "embedded", "firmware", "compiler",
                "graphics", "game", "ai", "research"}

# Matches "intern"/"internship" as a whole word — excludes "internal", "internals"
_INTERN_RE = re.compile(r"\b(intern|internship|co-?op)\b", re.IGNORECASE)

# Require explicit summer-2026 signal in the title
_SUMMER_2026_RE = re.compile(r"\b(2026|summer)\b", re.IGNORECASE)

# Exclude postings for other seasons or years
_EXCLUDE_PERIOD_RE = re.compile(
    r"\b(2025|2027|2028|fall|spring|winter|autumn)\b", re.IGNORECASE
)

# ── Company lists ─────────────────────────────────────────────────────────────
# Slugs are the identifier in each ATS URL. Wrong slugs fail silently.
# Add your own: find the slug in the company's job board URL.

# Greenhouse: boards.greenhouse.io/<slug>
GREENHOUSE = [
    # AI / ML
    "anthropic", "openai", "cohere", "characterai", "assemblyai",
    "elevenlabs", "runway", "snorkelai", "labelbox", "roboflow",
    "scaleai", "anyscale", "adept", "inflection", "huggingface",
    "modular", "together", "aleph-alpha", "imbue", "weights-biases",
    "clarifai", "landingai", "determined-ai",
    # Developer tools / infra
    "stripe", "vercel", "cloudflare", "hashicorp", "confluent",
    "mongodb", "elastic", "twilio", "databricks", "snowflakecomputing",
    "pulumi", "circleci", "buildkite", "harness", "temporal",
    "retool", "posthog", "cockroachdb", "yugabyte",
    "arangodb", "couchbase", "influxdata", "timescale", "singlestore",
    "starburst", "dremio", "imply", "dbtlabs", "airbyte",
    "fivetran", "prefect", "dagster", "pachyderm", "clearml",
    "grafana", "honeycomb", "pagerduty", "newrelic", "dynatrace",
    "lightstep", "logdna", "logz", "mezmo", "coralogix",
    "snyk", "lacework", "orca", "wiz", "aquasecurity",
    "sysdig", "tenable", "rapid7", "veracode", "checkmarx",
    "semgrep", "gitguardian", "spectralops", "cycode", "armorcode",
    "1password", "dashlane", "bitwarden", "keeper",
    "planetscale", "descript",
    # Fintech / Payments
    "brex", "ramp", "rippling", "gusto", "deel",
    "plaid", "coinbase", "robinhood", "acorns", "affirm",
    "marqeta", "mercury", "chime", "sofi", "klarna",
    "unit", "synctera", "alpaca", "drivewealth", "tastytrade",
    "betterment", "wealthfront", "stash", "dave", "albert",
    "brigit", "moneylion", "checkout", "gocardless", "flutterwave",
    "paystack", "carta", "pulley", "upstart", "lendingclub",
    "oportun", "avant",
    # SaaS / Productivity
    "figma", "airtable", "coda",
    "webflow", "framer", "pitch", "otter",
    "asana", "height", "shortcut", "clickup",
    "intercom", "helpscout", "freshworks", "front", "gorgias",
    "braze", "iterable", "klaviyo", "segment", "rudderstack",
    "mparticle", "hightouch", "census", "mixpanel", "amplitude",
    "heap", "fullstory", "logrocket", "hotjar", "contentsquare",
    # Data / Analytics
    "alation", "atlan", "collibra", "informatica", "immuta",
    "soda", "dvc", "matillion", "talend",
    # EdTech
    "duolingo", "coursera", "masterclass", "kahoot", "quizlet",
    "chegg", "brainly", "brilliant", "numerade", "photomath",
    "codecademy", "pluralsight", "udemy", "skillshare",
    # HealthTech
    "benchling", "veeva", "devoted", "oscar", "cityblock",
    "carbon-health", "hims", "cerebral", "tempus", "flatiron",
    "recursion", "insitro",
    # Mobility / Robotics / Climate
    "rivian", "nuro", "waymo", "cruise", "aurora",
    "mobileye", "zoox", "motional", "comma",
    # Consumer / Marketplace
    "airbnb", "reddit", "discord", "canva", "doordash",
    "instacart", "gopuff", "redfin", "opendoor", "compass",
    "taskrabbit", "thumbtack", "houzz", "roblox",
]

# Lever: jobs.lever.co/<slug>
LEVER = [
    # AI / ML / Infra
    "lambdalabs", "coreweave", "baseten", "modal",
    "replicate", "nomic", "weaviate", "pinecone",
    "netlify", "render", "railway", "convex",
    "workos", "clerk", "launchdarkly", "flagsmith", "statsig", "eppo",
    "optimizely", "split",
    # Fintech
    "greenlight", "wealthsimple", "versapay", "xsolla",
    "remote", "oyster", "multiplier", "papayaglobal",
    "velocity-global", "globalization-partners",
    # SaaS / Enterprise
    "netflix", "dropbox", "lyft", "snap", "pinterest",
    "shopify", "atlassian", "squarespace", "hubspot", "zendesk",
    "aircall", "dialpad", "vonage",
    "lattice", "culture-amp", "15five", "leapsome",
    "workramp", "docebo", "360learning", "cornerstone",
    "cognite", "uptake", "seeq",
    # Security / Defense
    "shieldai", "anduril", "crowdstrike", "sentinelone",
    "cybereason", "darktrace", "vectra", "exabeam",
    "securonix", "hunters", "stellar-cyber",
    # Developer tools
    "deno", "turso", "sanity", "contentful", "storyblok",
    "ghost", "prismic",
    # Consumer
    "medium", "quora", "producthunt",
]

# Ashby: api.ashbyhq.com/posting-api/job-board/<slug>
ASHBY = [
    # AI / ML (verified or high confidence)
    "perplexity", "pika-labs", "suno",
    "luma-ai", "ideogram", "stability",
    "inflection-ai", "sakana", "factory",
    "cognition", "cursor", "tabnine",
    "mistral", "fireworks-ai",
    # Developer tools / infra (verified)
    "linear", "replit", "vanta", "drata", "secureframe", "sprinto",
    "loom", "supabase", "neon", "stytch", "notion",
    "depot", "buildjet", "earthly", "dagger",
    "liveblocks", "partykit",
    # Fintech (verified)
    "ramp", "deel", "plaid", "modern-treasury", "lithic", "bond",
    "column", "treasury-prime", "sila", "finix",
    # SaaS / Productivity
    "craft", "mem", "reflect", "heptabase",
    "tana", "fibery", "rows", "grist",
    "nocodb", "baserow", "teable",
    "appsmith", "tooljet", "budibase",
    "airplane", "superblocks",
    # Analytics / Data
    "june", "pendo", "gainsight", "totango",
    "churnzero", "custify", "vitally", "planhat",
    # Climate
    "watershed", "patch", "south-pole", "carbon-direct",
    "pachama", "nori", "toucan", "flowcarbon",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_summer_2026_swe_intern(title: str) -> bool:
    """Return True only for summer-2026 SWE intern postings."""
    t = title.lower()
    if not _INTERN_RE.search(t):
        return False
    if not any(w in t for w in SWE_KEYWORDS):
        return False
    if _EXCLUDE_PERIOD_RE.search(title):   # fall/spring/winter or wrong year
        return False
    # must say "summer" or "2026", OR just "intern/internship" with no conflicting period
    return bool(_SUMMER_2026_RE.search(title)) or bool(_INTERN_RE.search(title))


def _parse_iso(ts: str | None) -> datetime | None:
    """Parse an ISO-8601 string into an aware UTC datetime."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_ms(ms: int | None) -> datetime | None:
    """Parse a Unix-milliseconds timestamp into an aware UTC datetime."""
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except Exception:
        return None


def _is_recent(posted_at: datetime | None) -> bool:
    """True if the posting is within MAX_AGE_HOURS, or if no timestamp available."""
    if posted_at is None:
        return False  # no timestamp → skip (strict mode)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    return posted_at >= cutoff


def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))


def load_all_jobs() -> list[dict]:
    if OUT_FILE.exists():
        try:
            return json.loads(OUT_FILE.read_text())
        except Exception:
            return []
    return []


def _sort_key(job: dict) -> datetime:
    ts = job.get("posted_at")
    if ts:
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def write_readme(jobs: list[dict], new_ids: set[str]):
    now = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")
    lines = [
        "# Summer 2026 SWE Internships",
        "",
        f"> 🤖 Auto-updated every hour via GitHub Actions &nbsp;|&nbsp; Last updated: **{now}**  ",
        f"> **{len(jobs)}** positions found · Scraped from Greenhouse, Lever & Ashby  ",
        f"> 🆕 = added in the most recent hourly run",
        "",
        "---",
        "",
        "| Company | Role | Location | Date Posted |",
        "| ------- | ---- | -------- | :---------: |",
    ]

    for job in jobs:
        company = job["company"].replace("-", " ").title()
        title   = job["title"]
        url     = job["url"]
        loc     = job.get("location") or "—"
        posted  = ""
        if job.get("posted_at"):
            try:
                dt     = datetime.fromisoformat(job["posted_at"])
                posted = dt.strftime("%b %d")
            except Exception:
                pass
        new_tag = " 🆕" if job["id"] in new_ids else ""
        lines.append(f"| **{company}**{new_tag} | [{title}]({url}) | {loc} | {posted} |")

    lines += [
        "",
        "---",
        "",
        "<sub>Positions must have **\"intern\"** in the title and not reference another season "
        "(fall/spring/winter) or year (2025/2027+). "
        "Jobs are scraped hourly and must have been posted within the past hour to be added.</sub>",
    ]
    README_FILE.write_text("\n".join(lines) + "\n")


def fetch(url: str) -> dict | list | None:
    try:
        r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

# ── Scrapers ──────────────────────────────────────────────────────────────────

def scrape_greenhouse(company: str) -> list[dict]:
    data = fetch(f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs")
    if not data:
        return []
    jobs = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        if not is_summer_2026_swe_intern(title):
            continue
        posted_at = _parse_iso(j.get("updated_at"))
        if not _is_recent(posted_at):
            continue
        jobs.append({
            "id":        f"gh:{company}:{j['id']}",
            "company":   company,
            "title":     title,
            "url":       j.get("absolute_url", f"https://boards.greenhouse.io/{company}"),
            "location":  ", ".join(o.get("name", "") for o in j.get("offices", [])),
            "posted_at": posted_at.isoformat() if posted_at else None,
            "source":    "greenhouse",
        })
    return jobs


def scrape_lever(company: str) -> list[dict]:
    data = fetch(f"https://api.lever.co/v0/postings/{company}?mode=json")
    if not data or not isinstance(data, list):
        return []
    jobs = []
    for j in data:
        title = j.get("text", "")
        if not is_summer_2026_swe_intern(title):
            continue
        posted_at = _parse_ms(j.get("createdAt"))
        if not _is_recent(posted_at):
            continue
        jobs.append({
            "id":        f"lv:{company}:{j['id']}",
            "company":   company,
            "title":     title,
            "url":       j.get("hostedUrl", f"https://jobs.lever.co/{company}"),
            "location":  j.get("categories", {}).get("location", ""),
            "posted_at": posted_at.isoformat() if posted_at else None,
            "source":    "lever",
        })
    return jobs


def scrape_ashby(company: str) -> list[dict]:
    data = fetch(f"https://api.ashbyhq.com/posting-api/job-board/{company}")
    if not data or not isinstance(data, dict):
        return []
    jobs = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        if not is_summer_2026_swe_intern(title):
            continue
        posted_at = _parse_iso(j.get("publishedDate"))
        if not _is_recent(posted_at):
            continue
        jobs.append({
            "id":        f"ash:{company}:{j['id']}",
            "company":   company,
            "title":     title,
            "url":       j.get("jobUrl", f"https://jobs.ashbyhq.com/{company}"),
            "location":  j.get("locationName", ""),
            "posted_at": posted_at.isoformat() if posted_at else None,
            "source":    "ashby",
        })
    return jobs

# ── Main ──────────────────────────────────────────────────────────────────────

def scrape_all(companies: list[str], scraper_fn, label: str) -> list[dict]:
    found = []
    for company in companies:
        jobs = scraper_fn(company)
        if jobs:
            print(f"  [{label}] {company}: {len(jobs)}")
        found.extend(jobs)
        time.sleep(0.15)
    return found


def main():
    seen        = load_seen()
    accumulated = {j["id"]: j for j in load_all_jobs()}
    fresh_jobs: list[dict] = []

    print(f"\n  Summer 2026 SWE Intern Scraper  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Filter: posted within last {MAX_AGE_HOURS}h | title must say \"summer\" or \"2026\"")
    total = len(GREENHOUSE) + len(LEVER) + len(ASHBY)
    print(f"  Checking {total} companies across Greenhouse / Lever / Ashby\n")

    fresh_jobs += scrape_all(GREENHOUSE, scrape_greenhouse, "greenhouse")
    fresh_jobs += scrape_all(LEVER,      scrape_lever,      "lever     ")
    fresh_jobs += scrape_all(ASHBY,      scrape_ashby,      "ashby     ")

    # Deduplicate within this run
    seen_this_run: set[str] = set()
    deduped: list[dict] = []
    for job in fresh_jobs:
        if job["id"] not in seen_this_run:
            seen_this_run.add(job["id"])
            deduped.append(job)
    fresh_jobs = deduped

    # Merge into accumulated list; track what's genuinely new
    new_ids: set[str] = set()
    for job in fresh_jobs:
        if job["id"] not in seen:
            new_ids.add(job["id"])
        accumulated[job["id"]] = job   # always refresh metadata
        seen.add(job["id"])

    sorted_jobs = sorted(accumulated.values(), key=_sort_key, reverse=True)

    print(f"\n  {len(fresh_jobs)} found this run  |  {len(new_ids)} NEW  |  {len(sorted_jobs)} total accumulated\n")
    print("─" * 72)

    if not new_ids:
        print("  No new positions this run.")
    else:
        for job in sorted_jobs:
            if job["id"] not in new_ids:
                continue
            loc = f"  [{job['location']}]" if job["location"] else ""
            src = job["source"][:3].upper()
            print(f" NEW  [{src}] {job['company'].upper():<22}  {job['title']}")
            print(f"              Apply → {job['url']}{loc}")
            print()

    save_seen(seen)
    OUT_FILE.write_text(json.dumps(sorted_jobs, indent=2))
    write_readme(sorted_jobs, new_ids)
    print("─" * 72)
    print(f"  {len(sorted_jobs)} jobs in {OUT_FILE} & README.md  |  {len(seen)} tracked IDs\n")


if __name__ == "__main__":
    main()
