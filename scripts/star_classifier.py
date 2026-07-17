#!/usr/bin/env python3
"""
GitHub Stars Auto-Classifier

Fetches all starred repos for a user from the GitHub API and auto-classifies them
by topics, language, and description into human-readable categories.

Usage:
  # Classify only (no sync):
  python3 star_classifier.py liwmj

  # Classify + sync to GitHub Stars Lists:
  export GITHUB_TOKEN="ghp_xxx"   # needs 'user' scope
  python3 star_classifier.py liwmj --sync

  # CI mode (GitHub Actions): reads GH_STAR_TOKEN, auto-confirms, incremental
  python3 star_classifier.py liwmj --sync --ci

  # Dry-run: preview what would be synced:
  python3 star_classifier.py liwmj --sync --dry-run

Output:
  - stars_data.json        : raw fetched data (cache)
  - stars_categorized.md   : human-readable categorized list
  - stars_categorized.html : dark-themed HTML page

Token scopes:
  - read:user      : sufficient for fetching + classifying (no --sync)
  - user            : required for --sync (create/manage Stars Lists)

Requirements: Python 3.8+ (stdlib only, no pip install needed)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from collections import OrderedDict

# ─── Category Rules ──────────────────────────────────────────────────────────

# Each category has:
#   topics: topic keywords to match
#   languages: primary languages for this category
#   desc: description keywords (fallback)
#   priority: higher = matched first

CATEGORIES = OrderedDict([
    ("🤖 AI / ML / Data", {
        "topics": [
            "machine-learning", "deep-learning", "artificial-intelligence",
            "nlp", "natural-language-processing", "llm", "large-language-model",
            "ai", "pytorch", "tensorflow", "jupyter-notebook", "data-science",
            "data", "neural-network", "transformer", "gpt", "openai",
            "langchain", "rag", "embedding", "vector-database",
            "computer-vision", "reinforcement-learning", "ml", "jax",
        ],
        "languages": [],
        "desc": [
            "machine learning", "deep learning", "large language model",
            "neural network", "llm", "gpt", "transformer",
        ],
        "priority": 10,
    }),
    ("🌐 Frontend / Web", {
        "topics": [
            "react", "vue", "angular", "svelte", "nextjs", "nuxt",
            "frontend", "web", "javascript", "typescript", "css",
            "html", "dom", "webpack", "vite", "esbuild", "babel",
            "tailwindcss", "bootstrap", "material-ui", "ant-design",
            "single-page-app", "spa", "ssr", "server-side-rendering",
            "web-components", "pwa", "wasm", "webassembly",
        ],
        "languages": ["TypeScript", "JavaScript", "HTML", "CSS", "SCSS"],
        "desc": [
            "react component", "vue component", "frontend framework",
            "web application", "single page app",
        ],
        "priority": 9,
    }),
    ("🦀 Rust", {
        "topics": ["rust", "rust-lang", "cargo", "rust-library", "rust-crate"],
        "languages": ["Rust"],
        "desc": ["rust"],
        "priority": 9,
    }),
    ("🐍 Python", {
        "topics": ["python", "python3", "python-library", "python-package", "pypi", "pip"],
        "languages": ["Python"],
        "desc": ["python package", "python library"],
        "priority": 8,
    }),
    ("🐹 Go", {
        "topics": ["go", "golang", "go-library", "go-module"],
        "languages": ["Go"],
        "desc": ["go package", "golang"],
        "priority": 8,
    }),
    ("☕ Java / JVM", {
        "topics": ["java", "kotlin", "scala", "jvm", "spring", "maven", "gradle"],
        "languages": ["Java", "Kotlin", "Scala"],
        "desc": ["java", "jvm"],
        "priority": 7,
    }),
    ("🔧 C / C++", {
        "topics": ["c", "cpp", "c-plus-plus", "c++", "cmake", "c-library"],
        "languages": ["C", "C++"],
        "desc": ["c library", "c++"],
        "priority": 7,
    }),
    ("📱 Mobile", {
        "topics": [
            "swift", "ios", "android", "kotlin-multiplatform",
            "flutter", "react-native", "mobile", "swiftui", "uikit",
        ],
        "languages": ["Swift", "Kotlin", "Dart", "Objective-C"],
        "desc": ["ios app", "android app", "mobile app"],
        "priority": 7,
    }),
    ("🛠️ DevOps / Infra", {
        "topics": [
            "docker", "kubernetes", "k8s", "terraform", "devops",
            "ci-cd", "infrastructure", "cloud", "aws", "azure", "gcp",
            "helm", "ansible", "prometheus", "grafana", "nginx",
            "continuous-integration", "continuous-deployment",
            "infrastructure-as-code", "serverless",
        ],
        "languages": ["HCL", "Dockerfile", "Shell"],
        "desc": [
            "docker", "kubernetes", "terraform", "infrastructure",
            "ci/cd", "devops",
        ],
        "priority": 7,
    }),
    ("🔧 CLI / Terminal", {
        "topics": [
            "cli", "command-line", "terminal", "tui",
            "command-line-tool", "shell",
        ],
        "languages": [],
        "desc": ["command-line tool", "cli tool", "terminal"],
        "priority": 6,
    }),
    ("🎨 Design / UI / CSS", {
        "topics": [
            "design", "ui", "ux", "css-framework", "tailwind",
            "icons", "svg", "animation", "color",
        ],
        "languages": ["CSS", "SCSS", "Less"],
        "desc": ["design system", "ui kit", "icon set"],
        "priority": 6,
    }),
    ("📚 Docs / Awesome / Learning", {
        "topics": [
            "awesome", "awesome-list", "documentation",
            "tutorial", "book", "course", "guide", "cheatsheet",
            "learning", "interview", "roadmap", "best-practices",
        ],
        "languages": ["Markdown", "TeX"],
        "desc": ["awesome list", "curated list", "learning resource"],
        "priority": 6,
    }),
    ("📦 Libraries / SDKs", {
        "topics": ["library", "sdk", "framework", "api-client", "package"],
        "languages": [],
        "desc": ["library", "sdk"],
        "priority": 5,
    }),
    ("🔐 Security", {
        "topics": [
            "security", "cybersecurity", "encryption", "authentication",
            "hacking", "penetration-testing", "cryptography",
        ],
        "languages": [],
        "desc": ["security", "encryption", "auth"],
        "priority": 5,
    }),
    ("🗄️ Database", {
        "topics": [
            "database", "sql", "nosql", "postgresql", "mysql",
            "mongodb", "redis", "sqlite", "orm",
        ],
        "languages": ["SQL", "PLpgSQL"],
        "desc": ["database", "sql", "orm"],
        "priority": 5,
    }),
    ("🧩 Other", {
        "topics": [],
        "languages": [],
        "desc": [],
        "priority": 0,
    }),
])


def classify_repo(repo):
    """Classify a single repo into the best-matching category."""
    topics = [t.lower() for t in repo.get("topics", []) or []]
    language = (repo.get("language") or "").strip()
    description = (repo.get("description") or "").lower()
    full_name = (repo.get("full_name") or "").lower()
    name = (repo.get("name") or "").lower()

    best_cat = "🧩 Other"
    best_priority = 0

    for cat_name, rules in CATEGORIES.items():
        score = 0

        # Topic match (strongest signal)
        for topic in topics:
            if topic in rules["topics"]:
                score += 3
            else:
                for rule_topic in rules["topics"]:
                    if rule_topic in topic or topic in rule_topic:
                        score += 1
                        break

        # Language match
        if language and language in rules["languages"]:
            score += 2

        # Description match
        if description:
            for kw in rules["desc"]:
                if kw in description:
                    score += 1

        # Name/full_name match (weak)
        if name or full_name:
            for kw in rules["desc"]:
                if kw in name or kw in full_name:
                    score += 1

        if score > best_priority:
            best_priority = score
            best_cat = cat_name
        elif score == best_priority and rules["priority"] > 1:
            # Tie-breaking: use category priority
            for cn, cr in CATEGORIES.items():
                if cn == best_cat and cr["priority"] < rules["priority"]:
                    best_cat = cat_name
                    break

    return best_cat


# ─── GitHub API ───────────────────────────────────────────────────────────────

def github_api(path, token=None, per_page=100):
    """Call GitHub REST API with pagination, return all items."""
    all_items = []
    page = 1

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "star-classifier/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    while True:
        url = f"https://api.github.com{path}"
        params = urllib.parse.urlencode({"per_page": per_page, "page": page})
        full_url = f"{url}?{params}"

        req = urllib.request.Request(full_url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            print(f"  API Error {e.code}: {body[:200]}")
            if e.code == 401:
                print("  → Token may be invalid or expired.")
                sys.exit(1)
            if e.code == 403:
                print("  → Rate limited. Wait a few minutes or use a token.")
                sys.exit(1)
            raise

        if not data:
            break

        all_items.extend(data)
        page += 1

        # Respect rate limits
        time.sleep(0.1)

        if len(all_items) % 500 == 0:
            print(f"  Fetched {len(all_items)} ...")

    return all_items


def fetch_stars(username, token=None):
    """Fetch all starred repos for a user."""
    print(f"Fetching stars for {username} ...")
    return github_api(f"/users/{username}/starred", token=token)


def fetch_repo_details(full_name, token=None):
    """Fetch additional details for a single repo (topics, etc)."""
    return github_api(f"/repos/{full_name}", token=None)


# ─── Output ───────────────────────────────────────────────────────────────────

def generate_markdown(categorized, gen_time=None):
    """Generate a markdown report of categorized stars."""
    ts = gen_time or datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = []
    lines.append(f"# ⭐ GitHub Stars — Auto Categorized")
    lines.append(f"")
    lines.append(f"> Generated: {ts}")
    lines.append(f"> Total repos: {sum(len(v) for v in categorized.values())}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for cat_name, repos in categorized.items():
        if not repos:
            continue
        lines.append(f"## {cat_name} ({len(repos)})")
        lines.append(f"")

        for repo in repos:
            name = repo["full_name"]
            url = repo["html_url"]
            desc = repo.get("description") or ""
            lang = repo.get("language") or ""
            stars = repo.get("stargazers_count", 0)
            topics = repo.get("topics", []) or []

            line = f"- **[{name}]({url})**"
            if lang:
                line += f" `{lang}`"
            if stars:
                line += f" ⭐{stars}"
            if desc:
                line += f" — {desc[:120]}"
            if topics:
                topic_tags = " ".join(f"`{t}`" for t in topics[:5])
                line += f"  \n  {topic_tags}"

            lines.append(line)

        lines.append(f"")

    return "\n".join(lines)


def generate_html(categorized, gen_time=None):
    """Generate a minimal HTML page with categorized stars."""
    ts = gen_time or datetime.now().strftime('%Y-%m-%d %H:%M')
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>⭐ GitHub Stars - Categorized</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }}
  h1 {{ color: #58a6ff; }}
  h2 {{ color: #f0883e; margin-top: 30px; border-bottom: 1px solid #21262d; padding-bottom: 8px; }}
  .repo {{ padding: 8px 0; border-bottom: 1px solid #21262d; }}
  .repo a {{ color: #58a6ff; text-decoration: none; font-weight: 600; }}
  .repo a:hover {{ text-decoration: underline; }}
  .repo .desc {{ color: #8b949e; font-size: 0.9em; }}
  .repo .meta {{ font-size: 0.8em; color: #6e7681; margin-top: 2px; }}
  .repo .topics {{ margin-top: 3px; }}
  .repo .topics span {{ background: #21262d; color: #58a6ff; padding: 1px 6px; border-radius: 10px; font-size: 0.75em; margin-right: 3px; }}
  .lang {{ color: #f0883e; }}
  .stars {{ color: #e3b341; }}
  .toc a {{ color: #58a6ff; }}
</style>
</head>
<body>
<h1>⭐ GitHub Stars — Categorized</h1>
<p>Generated: {ts} | Total: {sum(len(v) for v in categorized.values())} repos</p>

<div class="toc">
<h3>Categories</h3>
<ol>
"""
    for cat_name, repos in categorized.items():
        if repos:
            html += f'  <li><a href="#{cat_name.replace(" ", "-")}">{cat_name}</a> ({len(repos)})</li>\n'

    html += "</ol>\n</div>\n"

    for cat_name, repos in categorized.items():
        if not repos:
            continue
        html += f'\n<h2 id="{cat_name.replace(" ", "-")}">{cat_name} ({len(repos)})</h2>\n'

        for repo in repos:
            name = repo["full_name"]
            url = repo["html_url"]
            desc = repo.get("description") or ""
            lang = repo.get("language") or ""
            stars = repo.get("stargazers_count", 0)
            topics = repo.get("topics", []) or []

            html += '<div class="repo">\n'
            html += f'  <a href="{url}">{name}</a>\n'
            if desc:
                html += f'  <div class="desc">{desc}</div>\n'
            meta_parts = []
            if lang:
                meta_parts.append(f'<span class="lang">{lang}</span>')
            if stars:
                meta_parts.append(f'<span class="stars">⭐ {stars}</span>')
            if meta_parts:
                html += f'  <div class="meta">{" · ".join(meta_parts)}</div>\n'
            if topics:
                html += '  <div class="topics">'
                html += " ".join(f"<span>{t}</span>" for t in topics[:5])
                html += "</div>\n"
            html += "</div>\n"

    html += "\n</body>\n</html>"
    return html


# ─── GraphQL Sync ─────────────────────────────────────────────────────────────

GQL_URL = "https://api.github.com/graphql"
STATE_FILE = "stars_state.json"
MAX_MUTATIONS_PER_RUN = 450  # stay well under 500/hour secondary rate limit


def gql_request(token, query, variables=None):
    """Send a single GraphQL request. Returns parsed JSON data."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "star-classifier/2.0",
    }
    body = {"query": query}
    if variables:
        body["variables"] = variables

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(GQL_URL, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        print(f"  GraphQL Error {e.code}: {body_text[:300]}")
        if e.code == 401:
            print("  → Token needs 'user' scope. Classic PAT with 'user' scope required for Lists.")
            print("  → Create at: https://github.com/settings/tokens")
            sys.exit(1)
        raise

    if "errors" in result:
        for err in result["errors"]:
            print(f"  GraphQL error: {err.get('message', str(err))}")
        sys.exit(1)

    return result["data"]


def fetch_existing_lists(token):
    """Fetch all existing Stars Lists for the authenticated user."""
    query = """
    query($cursor: String) {
      viewer {
        lists(first: 100, after: $cursor) {
          nodes {
            id
            name
            description
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    lists = []
    cursor = None
    while True:
        data = gql_request(token, query, {"cursor": cursor})
        viewer = data.get("viewer", {})
        lst = viewer.get("lists", {})
        lists.extend(lst.get("nodes", []))
        page_info = lst.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    return lists


def load_state():
    """Load sync state: {node_id: list_name} of already-synced repos."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    """Save sync state to file."""
    state["_updated"] = datetime.now().isoformat()
    state["_count"] = len(state) - 2  # exclude _updated and _count
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def create_list(token, name, description=""):
    """Create a new Stars List. Returns the list's GraphQL ID."""
    query = """
    mutation($name: String!, $desc: String!) {
      createUserList(input: {name: $name, description: $desc, isPrivate: false}) {
        list { id name }
      }
    }
    """
    data = gql_request(token, query, {"name": name, "desc": description})
    list_id = data["createUserList"]["list"]["id"]
    print(f"  ✅ Created list: {name}")
    return list_id


def sync_repos_to_list(token, list_id, repos, state, cat_name, dry_run=False, max_mutations=None):
    """
    Batch-add NEW repos to a list via aliased GraphQL mutations.
    Skips repos already recorded in state.
    Updates state after each batch.
    Returns: (added_count, remaining_repos_for_next_run)
    """
    BATCH_SIZE = 5
    new_repos = [r for r in repos if r.get("node_id", "") not in state]
    total_new = len(new_repos)

    if total_new == 0:
        return 0, 0

    # Honor per-run mutation cap (only in CI mode; None = no limit)
    if max_mutations is None:
        remaining = total_new
    else:
        remaining = min(max_mutations, total_new)
    to_process = new_repos[:remaining]
    deferred = max(0, total_new - remaining)
    done = 0
    mutations_used = 0

    while done < len(to_process):
        batch = to_process[done : done + BATCH_SIZE]
        mutation_lines = []

        for i, repo in enumerate(batch):
            node_id = repo.get("node_id", "")
            mutation_lines.append(
                f'  r{i}: updateUserListsForItem('
                f'input: {{itemId: "{node_id}", listIds: ["{list_id}"]}}) {{'
                f'    clientMutationId'
                f'  }}'
            )

        merged = "mutation {\n" + "\n".join(mutation_lines) + "\n}"

        if dry_run:
            names = ", ".join(r.get("full_name", "?") for r in batch)
            print(f"  [dry-run] Would add {len(batch)} to '{cat_name}': {names[:120]}...")
        else:
            gql_request(token, merged)
            mutations_used += len(batch)

        # Save progress after each batch
        for repo in batch:
            state[repo.get("node_id", "")] = cat_name
        save_state(state)

        done += len(batch)
        if len(to_process) > BATCH_SIZE:
            print(f"  {cat_name}: {min(done, len(to_process))}/{len(to_process)}")

        if done < len(to_process):
            time.sleep(2.0)  # throttle: ~30 req/min

    if deferred > 0:
        print(f"  ⏸️  {cat_name}: {deferred} repos deferred (hit {MAX_MUTATIONS_PER_RUN}/run cap)")

    return mutations_used, deferred


def prune_unstarred(token, current_repos, state, dry_run=False):
    """
    Remove repos from GitHub Lists if they are no longer starred.
    Also cleans up state entries.
    current_repos: all repos from the latest fetch.
    """
    current_ids = {r.get("node_id", "") for r in current_repos}
    orphaned = [(nid, cat) for nid, cat in state.items()
                if not nid.startswith("_") and nid not in current_ids]

    if not orphaned:
        return

    print(f"\n🧹 Pruning {len(orphaned)} un-starred repos from lists ...")
    batch = []
    for node_id, cat in orphaned:
        batch.append(f'  r{len(batch)}: updateUserListsForItem('
                     f'input: {{itemId: "{node_id}", listIds: []}}) '
                     f'{{ clientMutationId }}')
        if len(batch) >= 5:
            merged = "mutation {\n" + "\n".join(batch) + "\n}"
            if not dry_run:
                gql_request(token, merged)
            batch = []
            time.sleep(0.5)

    if batch:
        merged = "mutation {\n" + "\n".join(batch) + "\n}"
        if not dry_run:
            gql_request(token, merged)

    # Clean up state
    for node_id, _ in orphaned:
        del state[node_id]
    save_state(state)
    print(f"  ✅ Removed {len(orphaned)} repos from lists + state")


def sync_categories(token, categorized, state, dry_run=False, is_ci=False, all_repos=None):
    """
    Sync classified repos to GitHub Stars Lists.
    Creates one list per category, then incrementally adds only NEW repos.
    Skips 'Other' category.
    """
    print("\n🔄 Syncing to GitHub Stars Lists ...")
    if dry_run:
        print("  (DRY RUN — no changes will be made)\n")
    if is_ci:
        print(f"  (CI mode: max {MAX_MUTATIONS_PER_RUN} mutations/run)\n")

    # 0. Prune repos that were un-starred since last sync
    if all_repos:
        prune_unstarred(token, all_repos, state, dry_run=dry_run)

    # 1. Fetch existing lists
    print("  Fetching existing lists ...")
    existing = fetch_existing_lists(token)
    existing_map = {lst["name"]: lst["id"] for lst in existing}
    print(f"  Found {len(existing)} existing list(s)")

    # 2. Create/ensure lists for each category
    list_map = {}  # category_name -> list_id
    for cat_name, repos in categorized.items():
        if cat_name == "🧩 Other" or not repos:
            continue
        if cat_name in existing_map:
            list_map[cat_name] = existing_map[cat_name]
            print(f"  📋 Using existing list: {cat_name}")
        else:
            if dry_run:
                print(f"  [dry-run] Would create list: {cat_name} ({len(repos)} repos)")
                list_map[cat_name] = f"DRY-RUN-ID-{cat_name}"
            else:
                list_map[cat_name] = create_list(token, cat_name)
            time.sleep(0.5)

    # 3. Incrementally add NEW repos to lists
    total_added = 0
    total_deferred = 0
    max_mut = MAX_MUTATIONS_PER_RUN if (is_ci and not dry_run) else None
    mutations_left = max_mut

    for cat_name, list_id in list_map.items():
        repos = categorized[cat_name]
        added, deferred = sync_repos_to_list(
            token, list_id, repos, state, cat_name,
            dry_run=dry_run, max_mutations=mutations_left
        )
        total_added += added
        total_deferred += deferred
        if mutations_left is not None:
            mutations_left -= added
            if mutations_left <= 0:
                break

    if total_added > 0:
        print(f"\n  ✅ Added {total_added} repos in this run")
    if total_deferred > 0:
        print(f"  ⏸️  {total_deferred} repos remain — next run will continue")
    if total_added == 0 and total_deferred == 0:
        print(f"\n  ✅ All repos already synced — nothing to do")

    print("\n✅ Sync complete!")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    # Parse args
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    do_sync = "--sync" in flags
    dry_run = "--dry-run" in flags
    is_ci = "--ci" in flags

    if len(args) < 1:
        print("Usage: python3 star_classifier.py <github-username> [--sync] [--ci] [--dry-run]")
        print("       Set GITHUB_TOKEN or GH_STAR_TOKEN env var.")
        print()
        print("  --sync      Create/update GitHub Stars Lists")
        print("  --ci        CI mode: non-interactive, GH_STAR_TOKEN, incremental")
        print("  --dry-run   Preview sync without making changes (requires --sync)")
        sys.exit(1)

    username = args[0]

    # CI mode: read GH_STAR_TOKEN, no interactive prompts
    if is_ci:
        token = os.environ.get("GH_STAR_TOKEN") or os.environ.get("GITHUB_TOKEN") or None
    else:
        token = os.environ.get("GITHUB_TOKEN") or None

    if not token:
        print("⚠️  No token set. Unauthenticated: 60 req/hr limit.")
        print("   Create a token at: https://github.com/settings/tokens")
        if do_sync:
            print("   For --sync: token needs 'user' scope (classic PAT).")
            print("   For classify only: 'read:user' scope is enough.")
            sys.exit(1)
        else:
            print("   Scope needed: read:user (no other permissions)")
        print(f"   Then: export GITHUB_TOKEN='ghp_xxx'\n")
    elif do_sync and not is_ci:
        print("🔑 Token provided — ensure it has 'user' scope for Lists operations.\n")

    # 1. Fetch stars
    data_file = "stars_data.json"
    if is_ci:
        # CI mode: always fetch fresh
        repos = None
    elif os.path.exists(data_file):
        use_cached = input(f"📁 {data_file} found. Use cached data? [Y/n]: ").strip().lower()
        if use_cached in ("", "y", "yes"):
            with open(data_file, encoding="utf-8") as f:
                repos = json.load(f)
            print(f"Loaded {len(repos)} repos from cache.\n")
        else:
            repos = None
    else:
        repos = None

    if repos is None:
        try:
            repos = fetch_stars(username, token=token)
        except Exception as e:
            print(f"Error fetching stars: {e}")
            sys.exit(1)

        print(f"Total starred repos: {len(repos)}")

        if not repos:
            print("No starred repos found.")
            sys.exit(0)

        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(repos, f, ensure_ascii=False, indent=2)
        print("Saved raw data → stars_data.json")

    # 2. Classify
    print("Classifying ...")
    categorized = OrderedDict()
    for cat_name in CATEGORIES:
        categorized[cat_name] = []

    for i, repo in enumerate(repos):
        cat = classify_repo(repo)
        categorized[cat].append(repo)
        if (i + 1) % 200 == 0:
            print(f"  Classified {i + 1}/{len(repos)} ...")

    for cat in categorized:
        categorized[cat].sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)

    # 3. Summary
    print("\n📊 Category Summary:")
    for cat_name, repos in categorized.items():
        if repos:
            synced_in_state = 0
            if is_ci or do_sync:
                state = load_state()
                synced_in_state = sum(
                    1 for r in repos if r.get("node_id", "") in state
                )
            tag = ""
            if synced_in_state > 0 and synced_in_state < len(repos):
                tag = f"  (🆕 {len(repos) - synced_in_state} new)"
            elif synced_in_state == len(repos):
                tag = "  (✅ all synced)"
            print(f"  {cat_name}: {len(repos)}{tag}")

    # 4. Output files
    gen_time = state.get("_updated") if (is_ci or do_sync) else None
    md = generate_markdown(categorized, gen_time=gen_time)
    with open("stars_categorized.md", "w", encoding="utf-8") as f:
        f.write(md)
    print("\n✅ Markdown → stars_categorized.md")

    html = generate_html(categorized, gen_time=gen_time)
    with open("stars_categorized.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ HTML     → stars_categorized.html")

    other_count = len(categorized.get("🧩 Other", []))
    if other_count > 0:
        print(f"\n📝 {other_count} repos in '🧩 Other' — check for missing category rules.")

    # 5. Sync to GitHub Lists
    if do_sync:
        state = load_state()
        sync_categories(token, categorized, state, dry_run=dry_run, is_ci=is_ci, all_repos=repos)


if __name__ == "__main__":
    main()
