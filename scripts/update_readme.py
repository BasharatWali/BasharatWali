#!/usr/bin/env python3
"""Rewrite the "Latest repositories" block in README.md.

Lists the most recently created public, non-fork repos that have had at least
one push. The summary comes from the repo description, or from the first
paragraph of its README when no description is set. Standard library only.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

USER = "BasharatWali"
LIMIT = 5
HIDE_TOPIC = "hide-from-portfolio"
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN")
README = Path(__file__).resolve().parent.parent / "README.md"
START, END = "<!-- LATEST-REPOS:START -->", "<!-- LATEST-REPOS:END -->"


def api_get(url, raw=False):
    accept = "application/vnd.github.raw" if raw else "application/vnd.github+json"
    req = urllib.request.Request(url, headers={"User-Agent": "profile-readme-updater", "Accept": accept})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", "replace")
    return body if raw else json.loads(body)


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_published(repo):
    if repo["fork"] or repo["private"] or repo.get("archived"):
        return False
    if repo["name"].lower() in {USER.lower(), f"{USER}.github.io".lower()}:
        return False
    if HIDE_TOPIC in repo.get("topics", []):
        return False
    pushed_after_create = (parse_time(repo["pushed_at"]) - parse_time(repo["created_at"])).total_seconds() > 60
    return repo.get("size", 0) > 0 or pushed_after_create


def clean_inline(text):
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", text).strip()


def short(text, limit=150):
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = cut.rfind(". ")
    if end > limit * 0.5:
        return cut[: end + 1]
    return cut[: cut.rfind(" ")].rstrip(",;:") + "…"


def readme_bits(repo):
    """Return (title, first paragraph) from the repo README, or (None, None)."""
    try:
        md = api_get(f"{API}/repos/{USER}/{repo['name']}/readme", raw=True)
    except urllib.error.HTTPError:
        return None, None
    h1 = re.search(r"^#\s+(.+?)\s*#*\s*$", md, re.M)
    title = clean_inline(h1.group(1)) if h1 else None
    body = re.sub(r"```.*?```|<!--.*?-->", "", md, flags=re.S)
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block or re.match(r"^(#|<|!\[|\||>|[-*+]\s|\d+\.\s|\[!\[|---|===)", block):
            continue
        summary = clean_inline(block)
        if len(summary) >= 40:
            return title, summary
    return title, None


def render(repos):
    lines = []
    for repo in repos:
        title, summary = readme_bits(repo)
        if not title or len(title) > 70:
            title = re.sub(r"[-_]+", " ", repo["name"]).strip()
        about = repo.get("description") or summary or "New project, write-up coming soon."
        meta = " · ".join(x for x in [repo.get("language"), parse_time(repo["created_at"]).strftime("%b %Y")] if x)
        lines.append(f"- **[{title}]({repo['html_url']})**: {short(about)} <sub>{meta}</sub>")
    return "\n".join(lines)


def main():
    repos = api_get(f"{API}/users/{USER}/repos?per_page=100&type=owner&sort=created")
    latest = [r for r in repos if is_published(r)]
    latest.sort(key=lambda r: r["created_at"], reverse=True)
    block = render(latest[:LIMIT])

    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        sys.exit(f"Markers {START} / {END} not found in README.md")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    new_text = pattern.sub(lambda _: f"{START}\n{block}\n{END}", text)
    if new_text != text:
        README.write_text(new_text, encoding="utf-8")
        print("README.md updated")
    else:
        print("No changes")


if __name__ == "__main__":
    main()
