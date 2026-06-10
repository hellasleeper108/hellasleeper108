#!/usr/bin/env python3
"""Generate dynamic sections for the hellasleeper108 GitHub profile README.

No third-party dependencies. Designed for both local runs and GitHub Actions.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USERNAME = "hellasleeper108"
ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
API = "https://api.github.com"

START = "<!-- LATEST-TRANSMISSIONS:START -->"
END = "<!-- LATEST-TRANSMISSIONS:END -->"
LANG_START = "<!-- SIGNAL-MAP:START -->"
LANG_END = "<!-- SIGNAL-MAP:END -->"

LANG_COLORS = {
    "Python": "39ff14",
    "Rust": "ff6b35",
    "JavaScript": "f7df1e",
    "TypeScript": "3178c6",
    "HTML": "e34f26",
    "CSS": "1572b6",
    "Shell": "89e051",
    "Jupyter Notebook": "da5b0b",
}


def request_json(path: str) -> Any:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    req = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{USERNAME}-profile-readme-generator",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub API error {exc.code} for {path}: {body}") from exc


def fetch_repos() -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = request_json(
            f"/users/{USERNAME}/repos?per_page=100&page={page}&sort=updated&type=owner"
        )
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [
        r
        for r in repos
        if not r.get("fork")
        and not r.get("archived")
        and r.get("name") != USERNAME
        and not r.get("private")
    ]


def fmt_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def repo_row(repo: dict[str, Any]) -> str:
    name = repo["name"]
    desc = (repo.get("description") or "No description yet — classified transmission.").replace("\n", " ")
    desc = desc.replace("|", "\\|")
    lang = (repo.get("language") or "mixed").replace("|", "")
    updated = fmt_date(repo["updated_at"])
    return f"| [`{name}`]({repo['html_url']}) | {desc} | `{lang}` | `{updated}` |"


def build_latest(repos: list[dict[str, Any]]) -> str:
    # Bias toward fresh active work, while keeping featured systems near the top if recently touched.
    recent = sorted(repos, key=lambda r: r.get("updated_at", ""), reverse=True)[:8]
    lines = [
        "| Transmission | Signal | Stack | Last ping |",
        "|---|---|---:|---:|",
        *[repo_row(r) for r in recent],
        "",
        "<sub>Auto-refreshed from public repo metadata by `.github/workflows/update-profile.yml`.</sub>",
    ]
    return "\n".join(lines)


def shield(label: str, value: str, color: str) -> str:
    def enc(s: str) -> str:
        return urllib.parse.quote(s.replace("-", "--"), safe="")

    return (
        f'<img alt="{label}: {value}" '
        f'src="https://img.shields.io/badge/{enc(label)}-{enc(value)}-{color}'
        f'?style=flat-square&labelColor=0d1117">'
    )


def build_signal_map(repos: list[dict[str, Any]]) -> str:
    langs = Counter(r.get("language") or "Mixed" for r in repos)
    top = langs.most_common(8)
    repo_count = len(repos)
    lines = ["<p>"]
    lines.append(f"  {shield('public systems', str(repo_count), '00e5ff')}")
    for lang, count in top:
        color = LANG_COLORS.get(lang, "b967ff")
        lines.append(f"  {shield(lang, str(count), color)}")
    lines.append("</p>")
    return "\n".join(lines)


def replace_between(text: str, start: str, end: str, content: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    block = f"{start}\n{content}\n{end}"
    if pattern.search(text):
        return pattern.sub(block, text)
    raise SystemExit(f"Missing README markers: {start} / {end}")


def main() -> int:
    text = README.read_text(encoding="utf-8")
    repos = fetch_repos()
    if not repos:
        raise SystemExit("No public repositories returned from GitHub API.")

    text = replace_between(text, START, END, build_latest(repos))
    text = replace_between(text, LANG_START, LANG_END, build_signal_map(repos))
    README.write_text(text, encoding="utf-8", newline="\n")
    print(f"Updated README.md from {len(repos)} public source repositories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
