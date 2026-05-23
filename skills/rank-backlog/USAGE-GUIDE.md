# Rank Backlog Skill - Usage Guide

## Quick Start

### Recommended (If gus-mcp server is available)
```bash
/rank-backlog "Your Team Name"
```
Simple! The skill automatically queries all team backlog items.

### Fallback (If gus-mcp server is NOT available)
```bash
/rank-backlog "Your Team Name" --users=email1@salesforce.com,email2@salesforce.com,email3@salesforce.com
```
Requires team member emails but still works well.

---

## Two Modes Explained

The skill automatically detects which mode to use based on your MCP server configuration:

### Mode 1: Natural Language Query (RECOMMENDED)

**Requirements:** gus-mcp MCP server configured

**How it works:**
- Single query: "List all backlog work items for team {name}"
- Retrieves ALL team backlog items directly
- No need for team member emails

**Usage:**
```bash
/rank-backlog "Pardot - Marketing AI and Data Alignment"
```

**Output:**
```
Analysis Mode: natural-language-query
✓ Used GUS natural language query (gus-mcp server)
Found 482 backlog items for team...
```

**Benefits:**
- ✅ Complete team coverage (all backlog items)
- ✅ Simple command (no email lists needed)
- ✅ Fast execution (~30 seconds for 482 items)
- ✅ Includes unassigned work
- ✅ Automatic - no manual setup per run

### Mode 2: Multi-User Query (FALLBACK)

**Requirements:** Team member emails

**How it works:**
- Queries each team member's backlog individually
- Aggregates and deduplicates results
- Filters to team's product tags

**Usage:**
```bash
/rank-backlog "Pardot - Marketing AI and Data Alignment" --users=michael.meeks@salesforce.com,avigad.mizrahi@salesforce.com,jason.osborne@salesforce.com
```

**Output:**
```
Analysis Mode: multi-user-query
Users queried: 3
Found 38 backlog items across 3 users...
```

**Limitations:**
- ⚠️ Only finds work assigned to specified users
- ⚠️ Misses unassigned work
- ⚠️ Requires maintaining email list
- ⚠️ Slower (multiple API calls)

---

## Checking Which Mode You Have

### Quick Check
Run the skill with your team name:

```bash
/rank-backlog "Your Team Name"
```

**If you see:**
- `Analysis Mode: natural-language-query` → You have gus-mcp! 🎉
- `Error: Please provide --users flag` → You need fallback mode

### Manual Check
Check available MCP servers:

```bash
# Ask Claude
"What MCP servers are available?"
```

Look for **gus-mcp** in the list. If it's there, you can use natural language mode!

---

## Setting Up gus-mcp Server (Recommended)

The gus-mcp server provides the best experience. If you don't have it configured:

### Option 1: Request from Your Admin
Contact your Claude Code administrator and request:
- **Server name:** gus-mcp
- **Tool needed:** query_gus_records
- **Use case:** Team-wide backlog analysis

### Option 2: Check Internal Documentation
Search internal Salesforce docs for:
- "gus-mcp MCP server setup"
- "GUS natural language query tool"
- "Claude Code MCP server configuration"

### Option 3: Use Fallback Mode
Continue using `--users=` flag until gus-mcp is available.

**See:** [GUS-MCP-SETUP.md](./GUS-MCP-SETUP.md) for detailed setup instructions

---

## Using Multi-User Fallback Mode

If gus-mcp is not available, you'll need team member emails.

### Getting Team Member Emails

**Method 1: Slack**
1. Go to your team's Slack channel
2. Click the channel name at the top
3. View member list
4. Emails are usually: firstname.lastname@salesforce.com

**Method 2: GUS Team Page**
1. Navigate to your team in GUS
2. Find "Team Members" section
3. Copy usernames/emails

**Method 3: Org Chart**
1. Use Salesforce internal org chart tool
2. Navigate to your team
3. Export team member list

**Method 4: Ask Your Manager**
Your EM likely has a complete team roster with emails.

### Formatting the Command

```bash
/rank-backlog "Team Name" --users=email1@salesforce.com,email2@salesforce.com,email3@salesforce.com
```

**Important:**
- No spaces after commas
- Use full email addresses (firstname.lastname@salesforce.com)
- Include all active team members for best results

**Example:**
```bash
/rank-backlog "Pardot - Marketing AI and Data Alignment" --users=michael.meeks@salesforce.com,avigad.mizrahi@salesforce.com,jason.osborne@salesforce.com,nir.tzavchon@salesforce.com
```

---

## Understanding the Output

### CSV File Structure

The generated CSV has 11 columns:

1. **Rank** - Priority ranking (1 = highest)
2. **Work ID** - GUS W-number
3. **Link** - Clickable GUS URL
4. **Subject** - Work item title
5. **Assigned To** - Current assignee
6. **Created Date** - When the item was created
7. **Age (Days)** - Days since creation
8. **Customer/Case Count** - Number of affected customers (if available)
9. **Days Since Last Activity** - Days since last modification
10. **Nevering Score** - Calculated priority score
11. **Recommendation** - Why this should be considered for nevering

### Priority Levels

- **Critical (Score ≥ 100)**: Linked to completed/nevered epics - safe to never immediately
- **High (Score ≥ 80)**: Zero customer impact - minimal risk to never
- **Medium (Score ≥ 60)**: Low impact + old/inactive - review before nevering
- **Lower (Score < 60)**: May still have value - discuss with team

### Example Output

```
========================================
Backlog Nevering Analysis for Team: Pardot - Marketing AI and Data Alignment
Date: 2026-02-26
Analysis Mode: natural-language-query
========================================

✓ Used GUS natural language query (gus-mcp server)
✓ Retrieved team-scoped backlog items directly

Summary:
- Total items analyzed: 482
- Critical priority (auto-never): 23
- High priority: 67
- Medium priority: 142
- Lower priority: 250

Assignment Distribution:
- Unassigned: 45 items
- michael.meeks@salesforce.com: 67 items
- avigad.mizrahi@salesforce.com: 89 items
- ... (top 10 shown)

Top 10 Candidates for Nevering:
| Rank | Work ID | Subject | Assigned To | Score | Recommendation |
|------|---------|---------|-------------|-------|----------------|
| 1 | W-1234567 | Old feature from nevered epic | John Doe | 120 | Critical: Epic nevered |
| 2 | W-2345678 | Bug with zero customer cases | Jane Smith | 115 | Critical: Epic completed |
...
```

---

## Mode Comparison Table

| Feature | Natural Language Query | Multi-User Query |
|---------|----------------------|------------------|
| **Setup** | None | Team emails needed |
| **Completeness** | 100% (all team items) | Partial (assigned only) |
| **Speed** | Fast (~30s for 482) | Medium (~2-3 min) |
| **Unassigned Work** | ✅ Included | ❌ Missed |
| **Maintenance** | ✅ Automatic | ⚠️ Update emails when team changes |
| **Accuracy** | ✅ True team scope | ⚠️ Limited to specified users |
| **Requirements** | gus-mcp server | Team member emails |

---

## Best Practices

### 1. Use Natural Language Mode If Available

Always prefer natural language mode (gus-mcp) for:
- More complete results
- Simpler commands
- Better accuracy

### 2. Include All Team Members (Multi-User Mode)

If using fallback mode, include:
- All engineers (all levels)
- Tech leads
- Engineering managers (if they have assigned work)
- Product owners (if they triage bugs)

### 3. Review Before Nevering

**Never auto-never without review!** Even critical items should be verified:
- Check if the epic is truly completed/nevered
- Verify customer count is accurate
- Read the work item description
- Check for recent comments

### 4. Share Results with Team

Import the CSV to Google Sheets and:
- Share with team for collaborative review
- Add a "Team Decision" column (Never / Keep / Discuss)
- Use conditional formatting for priority levels
- Sort and filter by different criteria

### 5. Track Progress Over Time

Run the analysis quarterly:
- Compare backlog size over time
- Track successful nevering rate
- Identify chronic backlog items
- Adjust scoring thresholds based on team needs

---

## Detailed Examples

### Example 1: Simple Usage (gus-mcp available)

```bash
/rank-backlog "Pardot - Marketing AI and Data Alignment"
```

**What happens:**
1. Skill detects gus-mcp server is available
2. Sends natural language query to GUS
3. Retrieves all 482 backlog items for team
4. Analyzes and scores each item
5. Generates CSV with ranked results
6. Shows top 10 candidates in terminal

**Time:** ~60 seconds total

**Result:** Complete team backlog analysis

### Example 2: Fallback Mode (gus-mcp not available)

```bash
/rank-backlog "Pardot - Marketing AI and Data Alignment" --users=michael.meeks@salesforce.com,avigad.mizrahi@salesforce.com,jason.osborne@salesforce.com,nir.tzavchon@salesforce.com
```

**What happens:**
1. Skill detects gus-mcp not available, uses fallback
2. Queries backlog for each of 4 users
3. Aggregates and deduplicates results
4. Filters to team's product tags
5. Analyzes and scores each item (38 found)
6. Generates CSV with ranked results
7. Shows top 10 candidates in terminal

**Time:** ~2-3 minutes total

**Result:** Partial team backlog (only assigned to those 4 users)

### Example 3: Large Team (Multi-User Mode)

```bash
/rank-backlog "Platform Team" --users=user1@salesforce.com,user2@salesforce.com,user3@salesforce.com,user4@salesforce.com,user5@salesforce.com,user6@salesforce.com,user7@salesforce.com,user8@salesforce.com
```

**What happens:**
1. Queries backlog for 8 users
2. Displays progress: "Querying user 3/8..."
3. Aggregates ~120 items across all users
4. Analyzes and scores
5. Generates comprehensive report

**Time:** ~3-5 minutes total

**Result:** Good coverage of team backlog

---

## Troubleshooting

### "Please provide --users flag" Error

**Cause:** gus-mcp server not available, fallback mode needs emails

**Solution:**
```bash
/rank-backlog "Team Name" --users=email1@salesforce.com,email2@salesforce.com
```

### "Team not found" Error

**Cause:** Team name doesn't match exactly

**Solution:**
1. Run skill without arguments to see available teams
2. Use exact team name (case-insensitive, but spelling must match)
3. Try partial name: "Pardot" instead of full name

### Very Few Results in Multi-User Mode

**Cause:** Only queried a few team members

**Solution:**
- Add more team members to --users list
- Get complete team roster from manager
- Request gus-mcp server setup for complete results

### "User not found" Warning

**Cause:** Email typo or user no longer with company

**Solution:**
- Double-check email spelling (firstname.lastname@salesforce.com)
- Remove inactive users from list
- Continue - skill will skip invalid users and process the rest

### Results Taking Too Long

**Cause:** Large backlog or many users in multi-user mode

**What to expect:**
- 100 items: ~1 minute
- 200 items: ~2 minutes
- 400 items: ~3-5 minutes

**What's happening:**
- Skill displays progress every 10 items
- Adds delays to avoid API rate limits
- This is normal for large backlogs

**Patience is key!** Let it complete.

---

## Advanced Usage

### Customizing Scoring Thresholds

Default thresholds (in SKILL.md):
- 5 cases: threshold for "low customer impact"
- 180 days: threshold for "old"
- 90 days: threshold for "inactive"

To adjust these for your team's needs:
1. Copy SKILL.md to create a custom version
2. Update Step 5 scoring algorithm
3. Document your custom thresholds
4. Use your custom skill version

### Filtering CSV Results in Google Sheets

After importing:

1. **Filter by Priority**
   - Create filter on "Nevering Score" column
   - Show only items ≥ 80 (High/Critical)

2. **Filter by Age**
   - Create filter on "Age (Days)" column
   - Show only items > 365 days (1+ years old)

3. **Filter by Assignee**
   - Create filter on "Assigned To" column
   - Group by team member for distribution

4. **Custom Views**
   - Sort by any column
   - Use conditional formatting for scores
   - Add comments for team decisions

### Automating Regular Analysis

Create a shell script for monthly runs:

```bash
#!/bin/bash
# monthly-backlog-analysis.sh

TEAM="Your Team Name"

# If gus-mcp available
claude-code "/rank-backlog \"$TEAM\""

# Or if using multi-user mode
# USERS="user1@sf.com,user2@sf.com,user3@sf.com"
# claude-code "/rank-backlog \"$TEAM\" --users=$USERS"

echo "Analysis complete! Check for CSV file."
```

Run monthly:
```bash
chmod +x monthly-backlog-analysis.sh
./monthly-backlog-analysis.sh
```

---

## FAQ

**Q: Why is gus-mcp better than multi-user mode?**

A: gus-mcp provides true team-scoped queries, finding ALL backlog items including unassigned work. Multi-user mode only finds work assigned to specific users.

**Q: Can I still use multi-user mode if I have gus-mcp?**

A: Yes! Add the `--users=` flag to force multi-user mode. Useful for testing or when you only want specific users' work.

**Q: How often should I run this analysis?**

A: Quarterly is recommended, or before major planning sessions when backlog grooming is important.

**Q: What if I don't have gus-mcp and can't get team emails?**

A: Start with your own backlog: `/rank-backlog "Team Name"` will analyze your assigned items. Then ask teammates to do the same and share CSVs to merge manually.

**Q: Can the skill create GUS tickets for nevering?**

A: No, the skill is read-only analysis. Nevering must be done manually in GUS after team review.

**Q: What happens to nevered items?**

A: They're marked as "Nevered" status in GUS, effectively closing them without doing the work. They can be reopened if needed later.

**Q: Can I modify the scoring algorithm?**

A: Yes! Edit the SKILL.md file, Step 5, to adjust scoring weights and thresholds for your team's needs.

**Q: Does the skill work for multiple teams?**

A: Yes, run it once per team. Each team gets its own CSV file.

---

## Getting Help

### Skill Issues
- Check this guide first
- Review GUS-MCP-SETUP.md for server configuration
- Check SKILL.md for detailed workflow
- Ask in #claude-code Slack channel (internal)

### GUS Issues
- Check GUS documentation
- Verify MCP server configuration
- Contact GUS support

### General Claude Code Help
```bash
/help
```

---

## Summary: Which Mode Should I Use?

### Use Natural Language Mode (gus-mcp) If:
- ✅ You have gus-mcp server configured
- ✅ You want complete team coverage
- ✅ You want the simplest command
- ✅ You want to include unassigned work

### Use Multi-User Fallback Mode If:
- ⚠️ You don't have gus-mcp server
- ⚠️ You can get team member emails
- ⚠️ You're okay with partial results
- ⚠️ You want to focus on specific team members only

### Request gus-mcp Setup If:
- 🎯 You do regular backlog analysis
- 🎯 You manage large backlogs (100+ items)
- 🎯 You want the best experience
- 🎯 You value accuracy and completeness

---

**Happy backlog cleaning!** 🧹

*Part of rank-backlog skill v2.0.0*
