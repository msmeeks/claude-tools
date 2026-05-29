# rank-backlog Skill

**Version:** 2.1.0
**Status:** Production Ready
**Last Updated:** 2026-02-26

## Quick Start

### With gus-mcp Server (Recommended)
```bash
/rank-backlog "Your Team Name"
```
That's it! Fully automatic.

### Without gus-mcp Server (Fallback)
```bash
/rank-backlog "Your Team Name" --users=email1@salesforce.com,email2@salesforce.com,email3@salesforce.com
```

## What It Does

Analyzes your team's GUS backlog to identify work items that should be "nevered" (dropped/deleted) based on:
- **Epic status**: Items linked to completed/nevered epics (highest priority)
- **Customer impact**: Zero or low customer cases reported
- **Age**: Items sitting in backlog for 180+ days
- **Inactivity**: No updates for 90+ days

**Output:** Ranked CSV file ready for Google Sheets import

## The Magic: Automatic Team Discovery

When the `gus-mcp` server is available, the skill:

1. **Automatically discovers your team members**
   - Queries: `ADM_Scrum_Team_Member__c`
   - Filters: 100% allocation + active status
   - Example: Found 7 members for Pardot - Marketing AI and Data Alignment

2. **Retrieves all team backlog items**
   - Natural language query: "List all backlog work items for team {name}"
   - Example: 482 items for Pardot team

3. **Analyzes and ranks for nevering**
   - Scores each item (0-120+ points)
   - Generates prioritized recommendations
   - Creates CSV with clickable GUS links

**No manual email lists. No outdated team rosters. Just works.**

## Evolution

### v1.0.0 → v1.1.0: Multi-Mode Support
- Added `--users` flag for multi-user queries
- Added product tag search (later removed - ineffective)
- Still limited to user-assigned work

### v1.1.0 → v2.0.0: Natural Language Queries
- Discovered gus-mcp server capabilities
- Added team-wide backlog queries (482 items!)
- Simplified to 2 modes: automatic vs manual

### v2.0.0 → v2.1.0: Team Member Auto-Discovery
- **Current version**
- Automatic team member discovery via gus-mcp
- No more `--users` flag needed
- Query: "List team members on '{team}' with 100% allocation"
- Result: 7 members discovered → 482 items analyzed

## Example Output

```
========================================
Backlog Nevering Analysis for Team: Pardot - Marketing AI and Data Alignment
Date: 2026-02-26
Analysis Mode: automatic-with-gus-mcp
========================================

✓ Automatically discovered 7 team members
✓ Used GUS natural language query (gus-mcp server)
✓ Retrieved team-scoped backlog items directly

Summary:
- Total items analyzed: 482
- Critical priority (auto-never): 23
- High priority: 67
- Medium priority: 142
- Lower priority: 250

Team Members (100% allocation):
- Michael Meeks
- Avigad Mizrahi
- Jason Osborne
- Nir Tzavchon
- [3 more...]

Top 10 Candidates for Nevering:
| Rank | Work ID | Subject | Score | Recommendation |
|------|---------|---------|-------|----------------|
| 1 | W-1234567 | Old feature from nevered epic | 120 | Critical: Epic nevered |
...

Full results saved to: backlog-nevering-analysis-pardot-maiday-2026-02-26.csv
```

## Files

```
~/.claude/skills/rank-backlog/
├── README.md (this file)         # Quick overview
├── SKILL.md                      # Main skill definition (586 lines)
├── USAGE-GUIDE.md                # Detailed user guide (546 lines)
├── GUS-MCP-SETUP.md              # gus-mcp server setup guide (204 lines)
├── examples/
│   └── sample-output.csv         # Example CSV output
└── templates/
    └── output-template.md        # Output format template
```

## Requirements

### Required
- `gus` MCP server (basic GUS operations)
- Standard Claude Code tools (Read, Write, Bash)

### Optional (Highly Recommended)
- `gus-mcp` MCP server (automatic mode)
  - Team member auto-discovery
  - Team-wide backlog queries
  - Natural language query interface

## Current Status

### Your Environment
- ✅ `gus` server: Available
- ❌ `gus-mcp` server: Not configured

### What This Means
- Skill will use **manual mode**
- You'll need to provide `--users` flag with team member emails
- Works fine, just less automatic

### To Upgrade
Request `gus-mcp` server setup from your Claude Code administrator.
**Reference:** Cursor has this configured successfully.
**See:** `GUS-MCP-SETUP.md` for details.

## Scoring Algorithm

```
score = 0

// Epic check (highest priority)
if (epic is completed/nevered) → +100 points

// Customer impact
if (customer_cases == 0) → +80 points
if (customer_cases < 5 AND age > 180 days) → +60 points

// Age factor
if (age > 365 days) → +20 points
if (age > 180 days) → +10 points

// Inactivity factor
if (inactive > 180 days) → +15 points
if (inactive > 90 days) → +10 points
```

**Priority levels:**
- Score ≥ 100: Critical (safe to never immediately)
- Score ≥ 80: High priority
- Score ≥ 60: Medium priority
- Score < 60: Lower priority (review case-by-case)

## CSV Output

11 columns:
1. Rank
2. Work ID
3. Link (clickable GUS URL)
4. Subject
5. Assigned To
6. Created Date
7. Age (Days)
8. Customer/Case Count
9. Days Since Last Activity
10. Nevering Score
11. Recommendation

**Import to Google Sheets:**
1. File → Import → Upload CSV
2. Links become clickable
3. Add "Team Decision" column for review
4. Share with team for collaborative nevering

## Best Practices

1. **Review before nevering** - Even critical items should be verified
2. **Share with team** - Use Google Sheets for collaborative review
3. **Run quarterly** - Track backlog cleanup progress over time
4. **Document decisions** - Add notes column for why items were/weren't nevered
5. **Check dependencies** - Verify no blocking relationships

## Common Questions

**Q: Does this actually never items in GUS?**
A: No, it's read-only analysis. You must manually never items in GUS after team review.

**Q: What if team members have <100% allocation?**
A: Use `--users` flag to include them manually, or the automatic query will still try team-wide backlog.

**Q: Can I customize the scoring thresholds?**
A: Yes! Edit SKILL.md Step 5 to adjust values (5 cases, 180 days, 90 days, etc.)

**Q: How long does it take?**
A: With gus-mcp: ~1-2 minutes for 482 items. Without: ~2-5 minutes depending on team size.

**Q: What if I don't have gus-mcp?**
A: Manual mode still works! Just provide team member emails with `--users` flag.

## Limitations

1. **100% allocation filter** - Auto-discovery only finds fully allocated members
2. **Active members only** - Excludes inactive/departed team members (desired)
3. **Customer/case count** - Field may not be accessible in all GUS configurations
4. **Permission-dependent** - Only shows work items you have access to
5. **Epic list limit** - Limited to 200 epics (GUS API)
6. **No real-time updates** - Snapshot at time of analysis

## Getting Help

- **Quick start:** This file
- **Detailed usage:** USAGE-GUIDE.md
- **Setup gus-mcp:** GUS-MCP-SETUP.md
- **Technical details:** SKILL.md

## Success Stories

**Pardot - Marketing AI and Data Alignment**
- 482 backlog items analyzed
- 7 team members discovered automatically
- 23 critical nevering candidates identified
- 67 high priority items flagged
- Ready for quarterly backlog cleanup

---

**Simple command. Powerful results. Happy nevering!** 🧹
