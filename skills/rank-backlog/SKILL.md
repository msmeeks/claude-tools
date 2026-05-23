---
name: rank-backlog
description: Identify and rank GUS work items that are candidates for nevering (deletion/dropping) based on customer impact, age, and activity. Use when user asks to analyze backlog, identify work to never, clean up old bugs, or prioritize backlog for deletion. Requires team name only - automatically discovers team members if gus-mcp server is available.
disable-model-invocation: true
allowed-tools: [mcp__gus__gus_list, mcp__gus__gus_work_list, mcp__gus__gus_work_get, mcp__google__docs_get, Read, Write, Bash, AskUserQuestion, ListMcpResourcesTool, ToolSearch]
version: 2.1.0
---

# Rank Backlog - Nevering Analysis Skill

Analyzes a team's GUS backlog to identify work items that are candidates for nevering (dropping/deleting) based on customer impact, age, and activity.

## 🎯 RECOMMENDED APPROACH

**Best experience: Just provide the team name!**

```bash
/rank-backlog "Team Name"
```

If the `gus-mcp` server is available, the skill will automatically:
1. Discover team members with 100% allocation
2. Query all team backlog items via natural language query
3. Analyze and rank items for nevering

**No need for team member emails - fully automatic!**

## Workflow

### Step 0: Check for Natural Language Query Tool

Check if the `gus-mcp` server with natural language query capability is available:

```
Call ListMcpResourcesTool() to get list of available servers
```

**If "gus-mcp" is in the server list:**
- Use **Mode A: Automatic with gus-mcp** (see Steps 2A and 3A below)
- This is the RECOMMENDED approach
- Fully automatic - no --users flag needed

**If "gus-mcp" is NOT available:**
- Parse arguments for `--users=` flag
- Use **Mode B: Manual Multi-User Query** (see Step 3B below)
- This is the FALLBACK approach
- Requires --users flag with team member emails

Display mode notification:
```
Analysis Mode: {automatic-with-gus-mcp | manual-multi-user}
Team: {team_name}
```

### Step 1: Validate Team

Retrieve the list of all teams and validate the provided team name:

```
Use ToolSearch to load: mcp__gus__gus_list
Call mcp__gus__gus_list(entity: "teams")
```

- If team argument is empty, display error: "Usage: /rank-backlog <team-name>"
- Search for team matching $ARGUMENTS (case-insensitive partial match)
- If not found, display available teams and exit with error
- Extract team ID and exact team name for further use

Display validation confirmation:
```
✓ Team validated: {team_name} (ID: {team_id})
Analysis Mode: {mode}
Proceeding with analysis...
```

### Step 2A: Discover Team Members (AUTOMATIC - if gus-mcp available)

**Use this step if `gus-mcp` server is available**

Use ToolSearch to load the natural language query tool:
```
ToolSearch query: "select:mcp__gus-mcp__query_gus_records"
```

Query team members with natural language:
```
Call mcp__gus-mcp__query_gus_records(
  query: "List team members on '{team_name}' with 100% allocation"
)
```

**What this does:**
- Queries ADM_Scrum_Team_Member__c object
- Filters by:
  - Scrum_Team__r.Name = '{team_name}'
  - Allocation__c = 100 (100% allocation)
  - Active__c = true
- Returns member records with Member_Name__c field

**Post-processing:**
- Extract member names from response
- Store list of team member usernames/emails
- Display: "Found {count} active team members with 100% allocation"
- If count is 0, display warning: "No team members found with 100% allocation. Will try team-wide backlog query."

**Example query executed by GUS:**
```sql
SELECT Id, Name, Member_Name__c, Member_Name__r.Name,
       Scrum_Team__c, Scrum_Team__r.Name
FROM ADM_Scrum_Team_Member__c
WHERE Scrum_Team__r.Name = 'Pardot - Marketing AI and Data Alignment'
  AND Allocation__c = 100
  AND Active__c = true
LIMIT 500
```

**Benefits:**
- ✓ Automatic team member discovery
- ✓ No manual email list maintenance
- ✓ Always up-to-date (reflects current team composition)
- ✓ Filters to fully allocated members only

### Step 2B: Collect Metadata (ALL MODES)

Retrieve epics to identify completed/nevered work:

```
Call mcp__gus__gus_list(entity: "epics")
```

- Build a set of epic IDs where status is "Completed", "Nevered", or "Closed"
- Store for later cross-referencing with work items
- Display: "Found {count} completed/nevered epics for filtering"

Retrieve product tags for the team:

```
Call mcp__gus__gus_list(entity: "product_tags")
```

- Filter product tags by team ID to get team's tags
- Store list of product tag IDs and names
- Display: "Found {count} product tags for team {team_name}"

### Step 3A: Retrieve Work Items - Automatic Mode (RECOMMENDED)

**Use this mode if `gus-mcp` server is available**

**Approach 1: Team-wide backlog query (preferred)**

Call the natural language query tool:
```
Call mcp__gus-mcp__query_gus_records(
  query: "List all backlog work items for team {team_name}"
)
```

Alternative natural language query formats that may work:
- "Show me all open bugs and user stories for team {team_name} in backlog"
- "Get backlog items (Bug, User Story) with status New, Triaged, In Progress, or Waiting for team {team_name}"
- "Find work items in backlog for {team_name}"

**Post-processing:**
- The tool may write results to a file (check the response for file path)
- If results are in a file, use Read tool to load them
- Parse the results to extract work item IDs (W-numbers)
- Display: "Found {count} backlog items for team {team_name} via natural language query"

**If team-wide query fails or returns 0 items:**

**Approach 2: Member-based queries (fallback within automatic mode)**

For each team member discovered in Step 2A:
```
Call mcp__gus__gus_work_list(
  user: "{member_email}",
  scope: "backlog",
  statuses: ["New", "Triaged", "In Progress", "Waiting"],
  types: ["Bug", "User Story"],
  limit: 500
)
```

- Display progress: "Querying backlog for team member {current}/{total}: {member_name}..."
- Aggregate all results into a single list
- Remove duplicates (same work item ID)
- Filter to only include items with product tags matching the team
- Display: "Found {count} total backlog items across {num_members} team members"

**Benefits of automatic mode:**
- ✓ True team-scoped queries (not limited to specific users)
- ✓ Can retrieve hundreds of items (tested with 482 items)
- ✓ No need to manually provide team member emails
- ✓ Automatic team member discovery
- ✓ Always uses current team composition

### Step 3B: Retrieve Work Items - Manual Multi-User Mode (FALLBACK)

**Use this mode if `gus-mcp` server is NOT available**

Parse $ARGUMENTS to extract user list:
```
if $ARGUMENTS contains "--users=":
  team_name = part before "--users="
  user_list = part after "--users=" (comma-separated)
else:
  Display error: "Manual mode requires --users flag"
  Display: "Usage: /rank-backlog '{team_name}' --users=email1@salesforce.com,email2@salesforce.com"
  Display: "Note: If you have access to gus-mcp server, you can omit --users flag for automatic team member discovery"
  Exit with error
```

For each user in user_list:
```
Call mcp__gus__gus_work_list(
  user: "{user_email}",
  scope: "backlog",
  statuses: ["New", "Triaged", "In Progress", "Waiting"],
  types: ["Bug", "User Story"],
  limit: 500
)
```

- Display progress: "Querying backlog for user {current}/{total}: {user_email}..."
- Aggregate all results into a single list
- Remove duplicates (same work item ID)
- Filter to only include items with product tags matching the team
- Display: "Found {count} total backlog items across {num_users} users for team {team_name}"

**Error handling:**
- If a user is not found or returns error, log warning and continue with other users
- If ALL users fail, display error and exit

**Limitations of this mode:**
- ⚠️ Requires manually providing team member emails
- ⚠️ Only finds work assigned to specified users (may miss unassigned work)
- ⚠️ Email list can become outdated when team changes
- ⚠️ Slower (multiple API calls)
- ⚠️ May hit API rate limits with many users

### Step 4: Enrich Work Item Details

For each work item found, fetch detailed information:

```
Call mcp__gus__gus_work_get(ref: "{work_id}")
```

**Extract the following fields:**

1. **Team Verification**: Verify the work item belongs to the target team
   - Look for team name or team ID in response
   - Check if product tag matches team's product tags
   - **Important:** If team doesn't match, EXCLUDE from analysis

2. **Created Date**: Look for `createdDate`, `CreatedDate`, `Created_Date__c`
   - Calculate: age_days = (today - created_date)

3. **Last Modified Date**: Look for `lastModifiedDate`, `LastModifiedDate`, `Last_Modified_Date__c`
   - Calculate: days_since_activity = (today - last_modified_date)

4. **Epic Linkage**: Look for `epic`, `Epic__c`, `parent_epic`, `related_epic`
   - Extract epic ID for cross-reference with completed/nevered epics

5. **Customer/Case Count**: Look for fields containing:
   - `Sum_of_Reported_Customers_and_Cases__c`
   - `Customer_Cases__c`
   - `Reported_Customers__c`
   - `Case_Count__c`
   - Any field with "customer", "case", "reported" in name
   - **Discovery approach**: On first work item, log all field names to identify pattern

6. **Subject**: Work item title
7. **Work ID**: W-number
8. **Type**: Bug or User Story
9. **Status**: Current status
10. **Assigned To**: Current assignee

**Progress indicator**: Display "Processing {current}/{total} items..." every 10 items

**Field fallback handling:**
- If customer/case count not found: Set to "N/A", adjust scoring to skip this factor
- If created date not found: Use earliest available timestamp
- If last modified not found: Use created date
- If epic not found: Skip epic scoring factor
- If team doesn't match: Exclude from results

**Rate limiting:**
- Add 100ms delay between individual `gus_work_get` calls
- If >100 items, display: "Large backlog detected. This may take 2-3 minutes..."

### Step 5: Calculate Nevering Score

Apply scoring algorithm to each work item:

```javascript
score = 0
recommendation = ""

// Epic check (highest priority)
if (epic_id in completed_or_nevered_epics) {
  score += 100
  recommendation = "Critical: Epic completed/nevered"
}

// Customer impact (if field available)
if (customer_case_count === 0) {
  score += 80
  if (!recommendation) recommendation = "High: Zero customer impact"
} else if (customer_case_count !== "N/A" && customer_case_count < 5) {
  if (age_days > 180) {
    score += 60
    if (!recommendation) recommendation = "Medium: Low impact + old"
  }
}

// Age factor
if (age_days > 365) {
  score += 20
} else if (age_days > 180) {
  score += 10
}

// Inactivity factor
if (days_since_activity > 180) {
  score += 15
} else if (days_since_activity > 90) {
  score += 10
}

// Default recommendation if none set
if (!recommendation) {
  if (score >= 60) {
    recommendation = "Medium: Old and inactive"
  } else if (score >= 40) {
    recommendation = "Lower: Consider for nevering"
  } else {
    recommendation = "Low priority"
  }
}
```

**Score interpretation:**
- Score >= 100: Critical (auto-never candidates)
- Score >= 80: High priority
- Score >= 60: Medium priority
- Score >= 40: Lower priority
- Score < 40: Low priority (keep for now)

Sort all work items by nevering_score descending (highest priority first)

### Step 6: Generate CSV Output

Create output file: `backlog-nevering-analysis-{team-slug}-{YYYY-MM-DD}.csv`

Where team-slug is a URL-friendly version of team name (lowercase, spaces to hyphens)

**CSV Structure:**
```csv
Rank,Work ID,Link,Subject,Assigned To,Created Date,Age (Days),Customer/Case Count,Days Since Last Activity,Nevering Score,Recommendation
1,W-12345678,https://gus.lightning.force.com/lightning/r/W-12345678/view,Example bug subject,john@salesforce.com,2023-05-15,620,0,450,100,Critical: Epic completed
```

**CSV Generation:**
```
Use Write tool to create CSV file with:
- Header row with all 11 column names
- One row per work item, sorted by rank
- Properly escaped fields (handle commas, quotes in subject)
- GUS link format: https://gus.lightning.force.com/lightning/r/{work_id}/view
```

**Special formatting:**
- Dates in ISO format (YYYY-MM-DD)
- Customer/Case Count as integer or "N/A"
- Subject: Escape quotes and commas for CSV compatibility
- Assigned To: Email or username or "Unassigned"

### Step 7: Generate Summary Output

Calculate summary statistics:
```javascript
total_items = work_items.length
critical_count = items where score >= 100
high_count = items where score >= 80 && score < 100
medium_count = items where score >= 60 && score < 80
lower_count = items where score < 60

// Calculate assignment distribution
assignment_counts = group by assigned_to
unassigned_count = items where assigned_to is null or empty
```

Display terminal output:

```
========================================
Backlog Nevering Analysis for Team: {team_name}
Date: {current_date}
Analysis Mode: {automatic-with-gus-mcp | manual-multi-user}
========================================

{If automatic mode:}
✓ Automatically discovered {team_member_count} team members
✓ Used GUS natural language query (gus-mcp server)
✓ Retrieved team-scoped backlog items directly

{If manual mode:}
ℹ️ Used manual multi-user mode (gus-mcp not available)
  Users queried: {user_count}
  Note: Results limited to work assigned to specified users
  Tip: Request gus-mcp server setup for automatic team member discovery

========================================

Summary:
- Total items analyzed: {total_items}
- Critical priority (auto-never): {critical_count}
- High priority: {high_count}
- Medium priority: {medium_count}
- Lower priority: {lower_count}

{If assignment data available:}
Assignment Distribution:
- Unassigned: {unassigned_count} items
- user1@salesforce.com: {count} items
- user2@salesforce.com: {count} items
- ... (top 10 assignees)

{If automatic mode with team members:}
Team Members (100% allocation):
- {member_name_1}
- {member_name_2}
- ... (all discovered members)

Methodology:
- Epic linkage: +100 points if linked to completed/nevered epic
- Customer impact: +80 points if 0 cases, +60 if <5 cases + old
- Age: +20 points if >365 days, +10 if >180 days
- Inactivity: +15 points if >180 days, +10 if >90 days

Top 10 Candidates for Nevering:
| Rank | Work ID | Subject | Assigned To | Score | Recommendation |
|------|---------|---------|-------------|-------|----------------|
{top_10_table_rows}

Full results saved to: backlog-nevering-analysis-{team-slug}-{date}.csv

To import to Google Sheets:
1. Open sheets.google.com
2. Click File > Import > Upload
3. Select the CSV file
4. Choose "Replace spreadsheet" or "Insert new sheet"
5. Links in column C will be clickable GUS URLs

Next Steps:
1. Review the CSV file for accuracy
2. Import to Google Sheets for collaborative review
3. Filter by "Critical" and "High" recommendations
4. Verify work items before nevering (check with team)
5. Use bulk nevering in GUS to process approved items

========================================
```

## Error Handling

**Team Not Found:**
```
Error: Team '{team_name}' not found.

Available teams:
- Team Alpha (id: a1b2c3)
- Team Beta (id: d4e5f6)
...

Usage: /rank-backlog <team-name>
```

**No Team Members Found (Automatic Mode):**
```
Warning: No team members found with 100% allocation for team '{team_name}'.

This could mean:
- Team members have < 100% allocation
- No active team members
- Team structure not configured in GUS

Attempting team-wide backlog query anyway...
```

**No Backlog Items:**
```
No backlog items found for team '{team_name}'.

This could mean:
- Team has no active bugs/stories in backlog statuses
- You may not have permissions to view team's work items
- {mode-specific explanation}

Try:
1. Verifying the team name is correct
2. Checking GUS permissions
3. {mode-specific suggestions}
```

**Natural Language Query Failed (Automatic Mode):**
```
Warning: Team-wide backlog query failed.
Falling back to member-based queries using discovered team members...

Querying {member_count} team members individually...
```

**No gus-mcp Server (Manual Mode Required):**
```
Error: gus-mcp server not available, manual mode required.

Please provide team member emails:
/rank-backlog "{team_name}" --users=email1@salesforce.com,email2@salesforce.com

To enable automatic mode:
- Request gus-mcp server setup from your Claude Code administrator
- See GUS-MCP-SETUP.md for details
```

**Invalid User (Manual Mode):**
```
Warning: User '{user_email}' not found or inaccessible. Skipping...
Continuing with remaining users...
```

**Missing Custom Fields:**
```
Note: Customer/case count field not available in GUS API response.
Ranking based on age, activity, and epic status only.
```

**API Rate Limits:**
- Add 100ms delay between individual `gus_work_get` calls
- Display "Rate limit encountered, slowing down..." if errors occur
- Retry failed requests once after 2-second delay

**Large Backlogs:**
- If >100 items, display progress every 10 items
- If >200 items, warn: "Large backlog detected. This may take 2-3 minutes..."

## Dependencies

**Required MCP Servers:**
- `gus` (always required) - for basic GUS operations

**Optional MCP Servers:**
- `gus-mcp` (highly recommended) - for automatic team member discovery and natural language query
  - Enables automatic mode (no --users flag needed)
  - Can retrieve 400+ work items
  - Discovers team members automatically
  - Always uses current team composition

**Required Tools:**
- mcp__gus__gus_list (for teams, epics, product_tags)
- mcp__gus__gus_work_get (for detailed work item data)
- Write (for CSV generation)
- Bash (for date calculations)
- ListMcpResourcesTool (for detecting available servers)
- ToolSearch (for loading MCP tools)

**Optional Tools:**
- mcp__gus-mcp__query_gus_records (from gus-mcp server) - HIGHLY RECOMMENDED
  - For automatic team member discovery
  - For team-wide backlog queries
- mcp__gus__gus_work_list (for fallback mode)
- AskUserQuestion (for interactive guidance)

## Usage

**Automatic mode (recommended - no setup needed if gus-mcp available):**
```
/rank-backlog "Team Name"
```
- Automatically discovers team members
- Retrieves all team backlog items
- No manual email list maintenance

**Manual mode (fallback if gus-mcp not available):**
```
/rank-backlog "Team Name" --users=email1@salesforce.com,email2@salesforce.com
```
- Requires manually providing team member emails
- Only finds work assigned to specified users

**Examples:**
- `/rank-backlog "Pardot - Marketing AI and Data Alignment"`
- `/rank-backlog "Platform Team"` (automatic if gus-mcp available)
- `/rank-backlog "Platform Team" --users=john@salesforce.com,jane@salesforce.com` (manual fallback)

## Limitations

1. **Server Availability**: Automatic mode requires gus-mcp server (not always available)
2. **Team Member Query**: Filters to 100% allocation only (may miss part-time members)
3. **Manual Mode Limitations**: Fallback mode only finds work assigned to specified users
4. **Field Discovery**: Customer/case count field may not be accessible
5. **Last Comment Date**: Approximated by last modified date
6. **Permission-Dependent**: Only shows work items visible to current user
7. **No Direct Google Sheets Creation**: Requires manual CSV import
8. **API Limits**: May hit rate limits with large backlogs (>200 items)
9. **Epic List Limit**: Limited to 200 epics (GUS API limitation)

## Output Files

**Primary Output:**
- `backlog-nevering-analysis-{team-slug}-{YYYY-MM-DD}.csv`

**Location:** Current working directory

**Format:** CSV with 11 columns, sorted by nevering score (descending)

## Version History

- **2.1.0** (2026-02-26): Automatic team member discovery
  - Added automatic team member discovery via gus-mcp
  - Query: "List team members on '{team}' with 100% allocation"
  - Filters by ADM_Scrum_Team_Member__c with Active__c = true
  - No longer requires --users flag when gus-mcp available
  - Simplified usage: just team name needed
  - Added ToolSearch to allowed tools

- **2.0.0** (2026-02-26): Major rewrite for natural language query
  - Added automatic detection of gus-mcp server
  - Prioritized natural language query mode (query_gus_records)
  - Simplified multi-user mode as fallback only
  - Removed product tag search mode (ineffective)
  - Tested with 482 items for Pardot team

- **1.1.0** (2026-02-26): Multi-mode update
  - Added multi-user mode (--users flag)
  - Added product tag search mode (--search-by-tags flag)
  - Added "Assigned To" column in CSV output

- **1.0.0** (2026-02-26): Initial implementation
  - Team validation
  - Epic linkage scoring
  - Age and inactivity scoring
  - CSV output generation
