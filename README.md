# Progress Tracker

**Know exactly what you built today, even when you forgot.**

## What It Does

Progress Tracker auto-discovers every git repo in your workspace, scans Claude Code session logs, checks file modifications, and compiles everything into a structured daily digest. It captures not just commits but also API-driven work, research, analysis, and conversation-driven output that never touches git. You can collect a day's activity, query past days, or generate weekly/monthly newsletters -- all from one command.

## How It Works

1. You type `/progress` or say "what did I do today"
2. The skill gathers data from five sources in parallel:
   - **Git repos (auto-discovered):** Runs `find` to locate every `.git` directory in the workspace -- no hardcoded project list. For each repo, pulls commits from the target date.
   - **Claude Code sessions:** Scans JSONL session files for user messages, file edits, bash commands, and tool calls. This is the richest source -- it captures API queries, analysis work, and research that produce no commits.
   - **File modifications:** Checks for files modified on the target date across the workspace, including output artifacts, memory files, and config changes.
   - **Memory file changes:** Reads new or modified memory files to extract project context (e.g., a new `project_sales_analysis.md` means that analysis was done).
   - **Ephemeral scripts:** Checks `/tmp/` for Python, JS, or shell scripts created that day (one-off tools, API classifiers, etc.).
3. All sources are synthesized into a daily digest grouped by project, with commit counts, narrative descriptions, and links to output artifacts
4. The digest is saved to `personal/progress-tracker/daily/YYYY-MM-DD.md`

For newsletters, the skill reads all daily digests in a date range and generates a summary with highlights, per-project breakdowns, metrics, and a forward-looking section.

## Key Features

- **Auto-discovery:** Finds every git repo dynamically -- new projects are captured automatically without updating a config
- **Session-aware:** Claude Code JSONL session logs are the primary data source, catching work that never results in a git commit (API calls, data analysis, Snowflake queries, research)
- **Five data sources:** Git commits, Claude sessions, file modifications, memory files, and ephemeral scripts -- nothing slips through
- **Daily digests:** Structured markdown files with frontmatter, grouped by project, with narrative descriptions beyond raw commit messages
- **Date queries:** Ask about any specific date or range ("what did I do last Tuesday", "show me last week")
- **Newsletter generation:** Weekly or monthly reports with highlights, metrics, and trajectory analysis
- **Backfill support:** Regenerate historical digests with `--since` and `--force` flags via the standalone backfill script
- **Background monitor:** Includes `progress_monitor.py` -- a universal progress bar renderer for long-running tasks
- **Noise filtering:** Regex-based patterns skip low-signal messages (IDE tags, one-word confirmations, system reminders)
- **IST timezone:** All timestamps converted to Indian Standard Time for accurate day boundaries

## Usage

### Skill (via Claude Code)

```
/progress                         # Collect today's activity
/progress collect                 # Same as above
/progress collect date=2026-04-28 # Collect a specific day
/progress date=2026-04-28         # Show what was done on that date
/progress yesterday               # Show yesterday's digest
/progress last week               # Show last 7 days
/progress range=30d               # Show last 30 days
/progress newsletter              # Generate weekly newsletter
/progress newsletter range=30d    # Generate monthly newsletter
```

**Trigger phrases:** "what did I do", "show progress", "daily digest", "collect today's progress", "generate newsletter", "weekly summary", "activity report"

### Backfill Script (standalone)

```bash
# Generate digests for all available history
python3 scripts/backfill.py

# Backfill from a specific date
python3 scripts/backfill.py --since 2026-04-01

# Overwrite existing digests
python3 scripts/backfill.py --force
```

The backfill script parses Claude Code JSONL session files, collects git commits across all tracked repositories, detects workspace config changes, and generates per-day markdown digests. It uses keyword classification to tag each activity to the correct project, deduplicates and filters noise, and supports the same IST timezone handling as the skill.

## Project Structure

```
SKILL.md               # Skill definition (Claude Code slash command)
progress_monitor.py    # Universal progress bar for background tasks
scripts/
  backfill.py          # Standalone backfill -- parses sessions, collects commits, generates digests
  cron.log             # Cron execution log
```

**Generated output (in workspace):**
```
personal/progress-tracker/
  daily/               # YYYY-MM-DD.md files (one per day)
  newsletters/         # Generated newsletter reports
```

## Tech Stack

- Python 3
- Standard library only (json, glob, subprocess, datetime, re, collections)
- Markdown output format

---

Built with [Claude Code](https://claude.ai/code) as a slash command skill.
