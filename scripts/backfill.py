#!/usr/bin/env python3
"""
Daily progress tracker — what Sarthak actually did in Claude Code, day by day.

Primary source: Claude session JSONL files (conversations, decisions, builds)
Secondary: git commits, file changes, workspace config updates

Usage:
    python3 backfill.py                    # backfill all available history
    python3 backfill.py --since 2026-03-01 # backfill from specific date
    python3 backfill.py --force            # overwrite existing digests
"""

import subprocess
import os
import sys
import json
import re
import glob
from datetime import datetime, timedelta, timezone
from collections import defaultdict

WORKSPACE = "/Users/sarthak/Claude"
DAILY_DIR = os.path.join(WORKSPACE, "personal/progress-tracker/daily")
SESSIONS_DIR = os.path.expanduser("~/.claude/projects/-Users-sarthak-Claude")
IST = timezone(timedelta(hours=5, minutes=30))

# Git repos (secondary source)
GIT_REPOS = {
    "flo-analytics-llm": os.path.join(WORKSPACE, ".claude/projects/flo-analytics-llm"),
    "myVoiceBooksAI": os.path.join(WORKSPACE, ".claude/projects/myVoiceBooksAI"),
    "myBillBook": os.path.join(WORKSPACE, "myBillBook"),
}

# All tracked projects — used to tag session messages
PROJECT_KEYWORDS = {
    "flo-analytics-llm": ["flo", "analytics", "rag", "sql-agent", "snowflake", "schema", "sdk"],
    "myVoiceBooksAI": ["voicebooks", "mvb", "voice", "tts", "stt", "otp", "mobile app"],
    "myBillBook": ["mybillbook", "mbb", "invoice", "animation", "airplane", "bill"],
    "trading-monitor": ["trading", "6e", "sierra", "dxy", "rsi", "divergence", "levels", "delta", "pivot", "backtest", "strategy", "scid"],
    "content-listener": ["content-listener", "vidtext", "transcrib", "youtube", "podcast", "chrome extension", "kindle", "reel", "instagram"],
    "claude-paglu": ["paglu", "claude-paglu", "remotion", "reel script", "storyboard", "infographic"],
    "workspace": ["agent", "skill", "claude.md", "memory", "pulse", "morning coffee", "progress"],
}

# Noise patterns to skip
NOISE_PATTERNS = [
    r"^\[Request interrupted",
    r"^\[Image:",
    r"^<task-notification>",
    r"^<ide_opened_file>.*</ide_opened_file>$",
    r"^(ok|yes|no|hmm|ah|oh|sure|thanks|cool|nice|great|done|good)\.?$",
    r"^give path",
    r"^where (can|do|is)",
    r"^this opened",
]


def run_cmd(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=30)
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def classify_project(text):
    """Tag a message with the project it's about."""
    text_lower = text.lower()
    matches = []
    for project, keywords in PROJECT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                matches.append(project)
                break
    return matches if matches else ["general"]


def is_noise(text):
    """Filter out low-signal messages."""
    if len(text) < 8:
        return True
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    return False


def clean_message(text):
    """Clean up a user message for display."""
    # Remove IDE tags
    text = re.sub(r"<ide_opened_file>.*?</ide_opened_file>\s*", "", text)
    text = re.sub(r"<ide_selection>.*?</ide_selection>", "", text, flags=re.DOTALL)
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL)
    text = text.strip()
    # Truncate
    if len(text) > 250:
        text = text[:250] + "..."
    return text


def parse_claude_sessions(since=None):
    """
    Parse all Claude session logs. Returns:
    {
        "YYYY-MM-DD": {
            "project-name": ["message1", "message2", ...],
            ...
        }
    }
    """
    if not os.path.exists(SESSIONS_DIR):
        return {}

    activity_by_date = defaultdict(lambda: defaultdict(list))

    for fpath in glob.glob(os.path.join(SESSIONS_DIR, "*.jsonl")):
        # Skip tiny files
        try:
            if os.path.getsize(fpath) < 1024:
                continue
        except OSError:
            continue

        try:
            with open(fpath, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Only user messages
                    if obj.get("type") != "user" and obj.get("role") != "user":
                        continue

                    ts = obj.get("timestamp", "")
                    if not ts:
                        continue

                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        dt_ist = dt.astimezone(IST)
                        date_str = dt_ist.strftime("%Y-%m-%d")
                    except (ValueError, TypeError):
                        continue

                    if since and date_str < since:
                        continue

                    # Extract text
                    msg = obj.get("message", {})
                    content = msg.get("content", "")
                    texts = []
                    if isinstance(content, str):
                        texts.append(content.strip())
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                texts.append(block.get("text", "").strip())

                    for text in texts:
                        cleaned = clean_message(text)
                        if not cleaned or is_noise(cleaned):
                            continue

                        projects = classify_project(cleaned)
                        for proj in projects:
                            activity_by_date[date_str][proj].append(cleaned)

        except (OSError, PermissionError):
            continue

    return dict(activity_by_date)


def dedupe_messages(messages):
    """Remove near-duplicate messages, keep order."""
    seen = set()
    result = []
    for msg in messages:
        key = msg.lower().strip()[:60]
        if key not in seen:
            seen.add(key)
            result.append(msg)
    return result


def get_git_commits_by_date(since=None):
    """Get git commits grouped by project and date. Secondary source."""
    result = {}
    for project_name, repo_path in GIT_REPOS.items():
        if not os.path.exists(os.path.join(repo_path, ".git")):
            continue
        cmd = ["git", "log", "--format=%ai|%s|%an", "--all"]
        if since:
            cmd.extend(["--since", since])
        output = run_cmd(cmd, cwd=repo_path)
        if not output:
            continue
        by_date = defaultdict(list)
        for line in output.split("\n"):
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            date = parts[0][:10]
            by_date[date].append(parts[1].strip())
        result[project_name] = dict(by_date)
    return result


def get_workspace_config_changes(since=None):
    """Track new/modified agents and skills."""
    config_dirs = [
        os.path.join(WORKSPACE, ".claude/agents"),
        os.path.join(WORKSPACE, ".claude/skills"),
    ]
    changes = defaultdict(list)
    for d in config_dirs:
        if not os.path.exists(d):
            continue
        for root, dirs, files in os.walk(d):
            for fname in files:
                if fname == ".DS_Store":
                    continue
                fpath = os.path.join(root, fname)
                try:
                    mtime = os.path.getmtime(fpath)
                    mod_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                    if since and mod_date < since:
                        continue
                    rel = os.path.relpath(fpath, WORKSPACE)
                    if "agents/" in rel:
                        changes[mod_date].append(f"Agent: {os.path.basename(fpath).replace('.md','')}")
                    elif "skills/" in rel:
                        # Extract skill name from path
                        parts = rel.split("/")
                        skill_name = parts[2] if len(parts) > 2 else os.path.basename(fpath)
                        changes[mod_date].append(f"Skill: {skill_name}")
                except OSError:
                    continue
    # Dedupe per date
    return {d: list(dict.fromkeys(items)) for d, items in changes.items()}


def format_date_header(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%B %d, %Y (%A)")


def generate_digest(date_str, session_data, git_data, config_data):
    """Generate daily digest — sessions first, git secondary."""
    day_sessions = session_data.get(date_str, {})
    sections = []
    projects_touched = []

    # ── CLAUDE WORK (primary) ──
    # Order: known projects first, then general
    project_order = [
        "flo-analytics-llm", "myVoiceBooksAI", "myBillBook",
        "trading-monitor", "content-listener", "claude-paglu",
        "workspace", "general",
    ]

    project_display = {
        "flo-analytics-llm": "Flo Analytics (SDK)",
        "myVoiceBooksAI": "MyVoiceBooksAI (App)",
        "myBillBook": "MyBillBook",
        "trading-monitor": "Trading Monitor (6E)",
        "content-listener": "Content Listener (VidText)",
        "claude-paglu": "Claude Paglu (Reels)",
        "workspace": "Workspace Setup",
        "general": "Other",
    }

    for proj in project_order:
        msgs = day_sessions.get(proj, [])
        if not msgs:
            continue
        deduped = dedupe_messages(msgs)
        if not deduped:
            continue

        projects_touched.append(proj)
        display_name = project_display.get(proj, proj)
        lines = [f"## {display_name}"]

        # Add git commits for this project if available
        commits = git_data.get(proj, {}).get(date_str, [])
        if commits:
            lines.append("**Commits:**")
            for c in commits:
                lines.append(f"- {c}")
            lines.append("")

        lines.append("**Work done:**")
        for msg in deduped[:12]:  # Cap at 12 items
            lines.append(f"- {msg}")

        sections.append("\n".join(lines))

    # Add git-only projects (commits but no conversation)
    for proj, dates in git_data.items():
        if proj in projects_touched:
            continue
        commits = dates.get(date_str, [])
        if commits:
            projects_touched.append(proj)
            display_name = project_display.get(proj, proj)
            lines = [f"## {display_name}", "**Commits:**"]
            for c in commits:
                lines.append(f"- {c}")
            sections.append("\n".join(lines))

    # Workspace config changes
    config_items = config_data.get(date_str, [])
    if config_items:
        if "workspace" not in projects_touched:
            projects_touched.append("workspace")
        lines = ["## Workspace Config"]
        for item in config_items:
            lines.append(f"- {item}")
        sections.append("\n".join(lines))

    # Nothing happened?
    if not sections:
        return None

    # Build digest
    active_list = ", ".join(projects_touched)
    commit_count = sum(len(git_data.get(p, {}).get(date_str, [])) for p in git_data)

    header = f"""---
date: {date_str}
projects_active: [{active_list}]
total_commits: {commit_count}
---

# {format_date_header(date_str)}
"""

    body = "\n\n".join(sections)
    return f"{header}\n{body}\n"


def main():
    force = "--force" in sys.argv
    since = None
    for i, arg in enumerate(sys.argv):
        if arg == "--since" and i + 1 < len(sys.argv):
            since = sys.argv[i + 1]

    os.makedirs(DAILY_DIR, exist_ok=True)

    # Primary: Claude sessions
    print("Parsing Claude session logs...")
    session_data = parse_claude_sessions(since)
    session_days = len(session_data)
    msg_count = sum(sum(len(v) for v in day.values()) for day in session_data.values())
    print(f"  Found {msg_count} messages across {session_days} days")

    # Secondary: git
    print("\nCollecting git commits...")
    git_data = get_git_commits_by_date(since)
    for proj, dates in git_data.items():
        count = sum(len(v) for v in dates.values())
        print(f"  {proj}: {count} commits")

    # Config changes
    print("\nCollecting workspace config changes...")
    config_data = get_workspace_config_changes(since)
    print(f"  {sum(len(v) for v in config_data.values())} changes")

    # All dates
    all_dates = set()
    all_dates.update(session_data.keys())
    for proj_dates in git_data.values():
        all_dates.update(proj_dates.keys())
    all_dates.update(config_data.keys())

    print(f"\nGenerating digests for {len(all_dates)} days...")
    created = 0
    skipped = 0

    for date_str in sorted(all_dates):
        filepath = os.path.join(DAILY_DIR, f"{date_str}.md")
        if os.path.exists(filepath) and not force:
            skipped += 1
            continue

        digest = generate_digest(date_str, session_data, git_data, config_data)
        if digest:
            with open(filepath, "w") as f:
                f.write(digest)
            created += 1
            print(f"  Created: {date_str}.md")

    print(f"\nDone! Created {created}, skipped {skipped} existing.")


if __name__ == "__main__":
    main()
