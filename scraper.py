#!/usr/bin/env python3
"""
CS Intern Summer 2026 Scraper
Hits Greenhouse / Lever / Ashby ATS APIs directly — no browser, no fragile selectors.
Covers SWE, PM, BA, data, QA, and other CS-adjacent intern roles.
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

SWE_KEYWORDS = {"software", "engineer", "swe", "developer", "backend",
                "frontend", "fullstack", "full-stack", "ml", "systems",
                "data", "infrastructure", "platform", "site reliability",
                "devops", "security", "embedded", "firmware", "compiler",
                "graphics", "game", "ai", "research"}

# Non-SWE but CS-adjacent roles (multi-word patterns that would be missed by SWE_KEYWORDS)
_CS_ROLE_RE = re.compile(
    r"\b("
    r"business\s+analyst"
    r"|product\s+manager"
    r"|project\s+manager"
    r"|program\s+manager"
    r"|technical\s+program"
    r"|solutions?\s+engineer"
    r"|data\s+analyst"
    r"|data\s+scientist"
    r"|quantitative\s+analyst"
    r"|it\s+(specialist|analyst|support)"
    r"|quality\s+assurance"
    r"|qa\s+engineer"
    r"|test\s+engineer"
    r"|ux\s+researcher"
    r"|information\s+(systems?|technology)"
    r")\b",
    re.IGNORECASE,
)

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

# Workday: (host, site, display_name)
# API: POST https://<host>/wday/cxs/<tenant>/<site>/jobs
WORKDAY = [
    ("nvidia.wd5.myworkdayjobs.com",      "NVIDIAExternalCareerSite", "nvidia"),
    ("amd.wd5.myworkdayjobs.com",         "External",                 "amd"),
    ("intel.wd1.myworkdayjobs.com",       "External",                 "intel"),
    ("qualcomm.wd5.myworkdayjobs.com",    "External",                 "qualcomm"),
    ("uber.wd5.myworkdayjobs.com",        "Uber_Careers",             "uber"),
    ("salesforce.wd12.myworkdayjobs.com", "Salesforce_Careers",       "salesforce"),
    ("linkedin.wd1.myworkdayjobs.com",    "jobs",                     "linkedin"),
    ("paypal.wd1.myworkdayjobs.com",      "jobs",                     "paypal"),
    ("adobe.wd5.myworkdayjobs.com",       "external_experienced",     "adobe"),
    ("oracle.wd1.myworkdayjobs.com",      "External",                 "oracle"),
    ("servicenow.wd5.myworkdayjobs.com",  "External",                 "servicenow"),
    ("workday.wd5.myworkdayjobs.com",     "External",                 "workday"),
    ("paloaltonetworks.wd1.myworkdayjobs.com", "External",            "palo-alto-networks"),
    ("fortinet.wd1.myworkdayjobs.com",    "External",                 "fortinet"),
    ("akamai.wd5.myworkdayjobs.com",      "External",                 "akamai"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

_HTML_TAG_RE = re.compile(r'<[^>]+>')

def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub(' ', text)


def is_cs_intern_title(title: str) -> bool:
    """Title must have intern + a SWE keyword or CS-adjacent role, with no conflicting period."""
    t = title.lower()
    return (bool(_INTERN_RE.search(t))
            and (any(w in t for w in SWE_KEYWORDS) or bool(_CS_ROLE_RE.search(t)))
            and not bool(_EXCLUDE_PERIOD_RE.search(title)))


def is_summer_2026(title: str, description: str = "") -> bool:
    """
    True if title+description together signal summer 2026 and nothing contradicts it.
    - Excludes if either mentions fall/spring/winter or a wrong year.
    - When a description is available, requires 'summer' or '2026' somewhere.
    - When no description is available (Workday etc.), passes on title alone.
    """
    combined = title + " " + description
    if _EXCLUDE_PERIOD_RE.search(combined):
        return False
    if description.strip():
        return bool(_SUMMER_2026_RE.search(combined))
    return True  # no description — rely on title filter + seen_jobs dedup


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
        "# Summer 2026 CS Internships",
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
        "<sub>Positions must have **\"intern\"** in the title plus a SWE keyword or CS-adjacent role "
        "(software engineer, product/project/program manager, business analyst, data analyst/scientist, QA engineer, solutions engineer, etc.). "
        "**\"summer\"** or **\"2026\"** must appear in the title or description where available. "
        "Postings mentioning fall/spring/winter or other years are excluded. "
        "Scraped hourly from Greenhouse, Lever, Ashby, Workday, Google, Amazon, Microsoft & Apple. "
        "🆕 = added since the previous run.</sub>",
    ]
    README_FILE.write_text("\n".join(lines) + "\n")


def fetch(url: str, params: dict | None = None) -> dict | list | None:
    try:
        r = requests.get(url, params=params, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def fetch_post(url: str, payload: dict) -> dict | None:
    try:
        r = requests.post(url, json=payload, timeout=8, headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
        })
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
        if not is_cs_intern_title(title):
            continue
        posted_at = _parse_iso(j.get("updated_at"))
        # Fetch full job to get description (one extra call, only for passing jobs)
        detail = fetch(f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{j['id']}")
        desc = _strip_html(detail.get("content", "")) if detail else ""
        if not is_summer_2026(title, desc):
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
        if not is_cs_intern_title(title):
            continue
        posted_at = _parse_ms(j.get("createdAt"))
        # Description is included in the listing response
        desc = j.get("descriptionPlain", "") or _strip_html(j.get("description", ""))
        if not is_summer_2026(title, desc):
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
        if not is_cs_intern_title(title):
            continue
        posted_at = _parse_iso(j.get("publishedDate"))
        # Description is included in the listing response
        desc = _strip_html(j.get("descriptionHtml", "") or j.get("description", ""))
        if not is_summer_2026(title, desc):
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

def scrape_google() -> list[dict]:
    data = fetch("https://careers.google.com/api/jobs/jobs-v1/search/", params={
        "q": "intern 2026",
        "employment_type": "INTERN",
        "page_size": 100,
        "hl": "en_US",
    })
    if not data:
        return []
    jobs = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        if not is_cs_intern_title(title):
            continue
        desc = _strip_html(j.get("description", ""))
        if not is_summer_2026(title, desc):
            continue
        loc = ", ".join(l.get("display", "") for l in j.get("locations", []))
        posted_at = _parse_iso(j.get("publish_date"))
        jobs.append({
            "id":        f"goog:{j.get('job_id', title[:60])}",
            "company":   "google",
            "title":     title,
            "url":       j.get("apply_url", "https://careers.google.com"),
            "location":  loc,
            "posted_at": posted_at.isoformat() if posted_at else None,
            "source":    "google",
        })
    return jobs


def scrape_amazon() -> list[dict]:
    data = fetch("https://www.amazon.jobs/en/search.json", params={
        "base_query":        "intern 2026",
        "result_limit":      100,
        "schedule_type_id[]": "Internship",
    })
    if not data:
        return []
    jobs = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        if not is_cs_intern_title(title):
            continue
        desc = _strip_html(j.get("description", ""))
        if not is_summer_2026(title, desc):
            continue
        posted_at = _parse_iso(j.get("posted_date"))
        jobs.append({
            "id":        f"amzn:{j.get('id_icims', j.get('job_id', title[:60]))}",
            "company":   "amazon",
            "title":     title,
            "url":       f"https://www.amazon.jobs{j.get('job_path', '')}",
            "location":  j.get("normalized_location", j.get("location", "")),
            "posted_at": posted_at.isoformat() if posted_at else None,
            "source":    "amazon",
        })
    return jobs


def scrape_microsoft() -> list[dict]:
    data = fetch("https://gcsservices.careers.microsoft.com/search/api/v1/search", params={
        "q":    "intern 2026",
        "l":    "en_us",
        "pg":   1,
        "pgSz": 100,
        "o":    "Relevance",
        "flt":  "true",
    })
    if not data:
        return []
    jobs = []
    for j in (data.get("operationResult", {})
                  .get("result", {})
                  .get("jobs", [])):
        title = j.get("title", "")
        if not is_cs_intern_title(title):
            continue
        desc = _strip_html(j.get("description", ""))
        if not is_summer_2026(title, desc):
            continue
        job_id    = j.get("jobId", "")
        posted_at = _parse_iso(j.get("postingDate"))
        jobs.append({
            "id":        f"msft:{job_id}",
            "company":   "microsoft",
            "title":     title,
            "url":       f"https://jobs.careers.microsoft.com/global/en/job/{job_id}",
            "location":  j.get("primaryLocation", ""),
            "posted_at": posted_at.isoformat() if posted_at else None,
            "source":    "microsoft",
        })
    return jobs


def scrape_apple() -> list[dict]:
    data = fetch("https://jobs.apple.com/api/role/search", params={
        "q":       "intern 2026",
        "filters": "STOREFRONT_ID%255B%255D%3DUSAF%2C1",
        "page":    1,
        "locale":  "en-US",
    })
    if not data:
        return []
    jobs = []
    for j in data.get("searchResults", []):
        title = j.get("postingTitle", "")
        if not is_cs_intern_title(title):
            continue
        desc = _strip_html(j.get("jobSummary", ""))
        if not is_summer_2026(title, desc):
            continue
        job_id    = j.get("positionId", "")
        posted_at = _parse_iso(j.get("postingDate"))
        jobs.append({
            "id":        f"aapl:{job_id}",
            "company":   "apple",
            "title":     title,
            "url":       f"https://jobs.apple.com/en-us/details/{job_id}",
            "location":  j.get("location", {}).get("name", ""),
            "posted_at": posted_at.isoformat() if posted_at else None,
            "source":    "apple",
        })
    return jobs


def scrape_workday(host: str, site: str, company: str) -> list[dict]:
    tenant = host.split(".")[0]
    data = fetch_post(
        f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
        {"appliedFacets": {}, "limit": 50, "offset": 0,
         "searchText": "intern 2026"},
    )
    if not data:
        return []
    jobs = []
    for j in data.get("jobPostings", []):
        title = j.get("title", "")
        if not is_cs_intern_title(title):
            continue
        # Workday listings don't include description — title-only check
        if not is_summer_2026(title):
            continue
        path      = j.get("externalPath", "")
        posted_at = None  # Workday returns relative strings like "Posted Today"
        jobs.append({
            "id":        f"wd:{company}:{path.split('/')[-1]}",
            "company":   company,
            "title":     title,
            "url":       f"https://{host}{path}",
            "location":  j.get("locationsText", ""),
            "posted_at": posted_at,
            "source":    "workday",
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

    print(f"\n  Summer 2026 CS Intern Scraper  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    ats_total = len(GREENHOUSE) + len(LEVER) + len(ASHBY) + len(WORKDAY)
    print(f"  Checking {ats_total} ATS companies + Google / Amazon / Microsoft / Apple\n")

    fresh_jobs += scrape_all(GREENHOUSE, scrape_greenhouse, "greenhouse")
    fresh_jobs += scrape_all(LEVER,      scrape_lever,      "lever     ")
    fresh_jobs += scrape_all(ASHBY,      scrape_ashby,      "ashby     ")
    fresh_jobs += scrape_all(
        [(h, s, c) for h, s, c in WORKDAY],
        lambda x: scrape_workday(*x),
        "workday   ",
    )

    print("  Scraping big-tech portals...")
    for fn, label in [
        (scrape_google,    "google   "),
        (scrape_amazon,    "amazon   "),
        (scrape_microsoft, "microsoft"),
        (scrape_apple,     "apple    "),
    ]:
        jobs = fn()
        if jobs:
            print(f"  [{label}] {len(jobs)}")
        fresh_jobs.extend(jobs)

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
