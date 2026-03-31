---
name: progress
description: "Use when someone says 'what did I do', 'show progress', 'daily digest', 'collect today's progress', 'generate newsletter', 'weekly summary', 'activity report', or asks about work done on a specific date."
user-invocable: true
argument-hint: "date=YYYY-MM-DD | range=7d | collect | newsletter | query='what did I work on last week?'"
---

# Progress Tracker

Track, query, and report on daily progress across all workspace projects.

## What This Skill Does

Manages a daily progress journal stored in `personal/progress-tracker/daily/`. Each day gets a structured markdown file capturing git commits, file changes, and project activity. You can:

- **Collect** today's (or any day's) activity into a daily digest
- **Query** what was done on a specific date or range
- **Newsletter** generate a weekly/monthly progress report

## Storage

```
personal/progress-tracker/
├── daily/           ← YYYY-MM-DD.md files (one per day)
├── newsletters/     ← Generated newsletter files
└── scripts/         ← Collection utilities
```

## Step 1: Parse Arguments

Parse `$ARGUMENTS` to determine the action:

| Argument | Action |
|----------|--------|
| `collect` or no args | Collect today's activity into a daily digest |
| `collect date=YYYY-MM-DD` | Collect activity for a specific date |
| `date=YYYY-MM-DD` | Show what was done on that date |
| `range=7d` or `range=30d` | Show activity for the last N days |
| `yesterday` | Show yesterday's activity |
| `last week` | Show last 7 days |
| `newsletter` | Generate newsletter for last 7 days |
| `newsletter range=30d` | Generate newsletter for last 30 days |
| Any natural language | Interpret as a query about activity |

## Step 2: Collect Activity (if collecting)

Spawn the **progress-tracker-agent** to collect activity for the target date(s).

**CRITICAL: Use ALL 4 data sources below. Never rely on only one. The hardcoded project list is NOT the source of truth — discovery is.**

### Source 1: Auto-discover ALL git repos (NOT a hardcoded list)

```bash
# Find EVERY git repo under the workspace — catches new projects created mid-day
find /Users/sarthak/Claude -name ".git" -type d -maxdepth 4 \
  -not -path "*/node_modules/*" -not -path "*/.venv/*" 2>/dev/null | \
  sed 's/\/.git$//'
```

For EACH discovered repo, run:
```bash
cd <repo_path> && git log --format="- %s" --after="YYYY-MM-DDT00:00:00" --before="YYYY-MM-DD+1T00:00:00"
```

For myBillBook specifically, filter to Sarthak's commits:
```bash
cd /Users/sarthak/Claude/work/myBillBook && git log --author="sarthak\|Sarthak" --format="- %s" --after="YYYY-MM-DDT00:00:00" --before="YYYY-MM-DD+1T00:00:00"
```

### Source 2: Claude Code session activity

This is the RICHEST source of what was actually worked on. Claude Code stores session logs as JSONL files.

```bash
# Find all session files modified on the target date
find /Users/sarthak/.claude/projects/-Users-sarthak-Claude -name "*.jsonl" \
  -newermt "YYYY-MM-DD 00:00" ! -newermt "YYYY-MM-DD+1 00:00" 2>/dev/null
```

For each session file found, extract a summary of work done:
```bash
# Extract user messages (what was asked) and tool calls (what was done)
# Look for: file writes/edits, bash commands, web fetches, agent spawns
cat <session_file> | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        obj = json.loads(line.strip())
        # Extract user messages
        if obj.get('type') == 'human' or obj.get('role') == 'user':
            content = obj.get('content', '')
            if isinstance(content, str) and len(content) > 10:
                print(f'USER: {content[:200]}')
            elif isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get('type') == 'text' and len(c.get('text','')) > 10:
                        print(f'USER: {c[\"text\"][:200]}')
        # Extract tool uses (file edits, writes, bash)
        if obj.get('type') == 'assistant' or obj.get('role') == 'assistant':
            content = obj.get('content', [])
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get('type') == 'tool_use':
                        name = c.get('name', '')
                        inp = c.get('input', {})
                        if name in ('Write', 'Edit'):
                            print(f'WROTE: {inp.get(\"file_path\", \"\")}')
                        elif name == 'Bash':
                            cmd = inp.get('command', '')[:150]
                            print(f'RAN: {cmd}')
    except: pass
" 2>/dev/null | head -100
```

Use these extracted messages to understand:
- What projects/topics were worked on (even if no git commits)
- API-driven work (LSQ calls, Amplitude queries, Snowflake queries)
- Scripts run in /tmp/ that aren't in any repo
- Analysis and research done conversationally

### Source 3: File modifications across workspace

```bash
# All modified files today (catches output/, memory, non-git projects)
find /Users/sarthak/Claude -type f -newermt "YYYY-MM-DD 00:00" ! -newermt "YYYY-MM-DD+1 00:00" \
  -not -path "*/.git/*" -not -path "*/__pycache__/*" -not -path "*/.venv/*" \
  -not -path "*/node_modules/*" -not -name "*.pyc" -not -name ".DS_Store" 2>/dev/null
```

Pay special attention to:
- `output/` directory — generated reports, dashboards, artifacts
- `personal/` directory — any new or modified project files
- `.claude/agents/` and `.claude/skills/` — workspace config changes
- `.claude/projects/-Users-sarthak-Claude/memory/` — new memory files = new work context

### Source 4: Memory file changes

```bash
# Check for new/modified memory files (these indicate new projects or learnings)
find /Users/sarthak/.claude/projects/-Users-sarthak-Claude/memory -type f \
  -newermt "YYYY-MM-DD 00:00" ! -newermt "YYYY-MM-DD+1 00:00" 2>/dev/null
```

Read each modified memory file to extract project context (e.g., a new `project_mbb_sales_touch_analysis.md` means LSQ analysis was done).

### Source 5: Ephemeral scripts in /tmp/

```bash
# Check for scripts created today in /tmp (API classifiers, one-off tools)
find /tmp -maxdepth 1 -name "*.py" -o -name "*.js" -o -name "*.sh" 2>/dev/null | \
  xargs ls -lt 2>/dev/null | head -10
```

## Step 3: Write Daily Digest

Synthesize ALL sources into `personal/progress-tracker/daily/YYYY-MM-DD.md` using this format:

```markdown
---
date: YYYY-MM-DD
projects_active: [project1, project2]
total_commits: N
---

# Daily Progress — Month DD, YYYY

## [Project Name] — N commits (if git-tracked)
[What was done — not just commit messages, but the actual narrative of what was built/analyzed/fixed]

- [Key commits or changes as bullet points]
- Files: [key files touched]

## [Analysis/Research Project] (no commits — API/conversation work)
[What was analyzed, what data was pulled, what the findings were]

- [Key findings or outputs]
- Output: [file paths to generated artifacts]

## Workspace Config
- [new/modified agents or skills]

---
**Summary:** [2-3 sentence highlight covering the full scope of the day]
```

**Rules:**
- Group by project, not by source
- Include commit counts where applicable
- For non-git work (API analyses, research), describe what was done and what was found
- Link to output artifacts where they exist
- Skip sections with genuinely no activity
- The summary MUST reflect the FULL scope — don't bury major work

## Step 4: Query (if querying)

1. Check if `personal/progress-tracker/daily/YYYY-MM-DD.md` exists
2. If yes, read and present it
3. If no, collect on the fly (Step 2-3), then present
4. For ranges, read all files in the range, group by project, summarize

## Step 5: Newsletter (if generating)

1. Read all daily digests in the requested range
2. Generate a newsletter with:
   - **Highlights** — top 3-5 achievements across projects
   - **By Project** — what happened in each project
   - **Metrics** — commits, projects active, most active project
   - **Looking Ahead** — based on trajectory and memory files
3. Save to `personal/progress-tracker/newsletters/YYYY-MM-DD-newsletter.md`
4. Also display the newsletter to the user

## Notes

- If a daily digest already exists, don't overwrite unless `collect --force` is passed
- For myBillBook, filter out commits by other team members unless specifically asked — focus on Sarthak's contributions
- The agent should be fast — don't read full file contents, only metadata, git logs, and session summaries
- NEVER rely solely on a hardcoded project list. Always auto-discover repos and scan sessions.
- Claude Code sessions are THE primary source of truth for what was worked on. Git commits alone miss API work, analysis, research, and conversation-driven output.
