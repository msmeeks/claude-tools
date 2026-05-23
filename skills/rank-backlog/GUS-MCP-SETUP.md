# GUS-MCP Server Setup Guide

## Overview

The `rank-backlog` skill works best with the **gus-mcp** server, which provides natural language query capabilities for GUS work items. This server can retrieve team-scoped backlog items directly without the limitations of the standard `gus` server.

## Why You Need It

### Standard `gus` Server (Limited)
- ❌ User-centric queries only (work assigned to specific users)
- ❌ Cannot query all work for a team
- ❌ Requires knowing team member emails
- ❌ Multiple API calls needed (one per user)

### `gus-mcp` Server (Recommended)
- ✅ Team-scoped queries via natural language
- ✅ Can retrieve 400+ work items directly
- ✅ No need for team member emails
- ✅ Single query gets all team backlog items
- ✅ Example: "List all backlog work items for team Pardot - Marketing AI and Data Alignment" → 482 items

## Verification

Check if you have the `gus-mcp` server configured:

### Method 1: Claude Code Tool Search
```
/ask-claude "List available MCP servers"
```

Look for "gus-mcp" in the server list. If you see it, you're good to go!

### Method 2: Direct Check
The `rank-backlog` skill automatically detects if the `gus-mcp` server is available and uses it if present.

## Current Status

**Your Environment:**
- ✅ `gus` server: Available (standard GUS tools)
- ❌ `gus-mcp` server: Not configured (natural language query)

**Impact:**
- The skill will use **multi-user fallback mode**
- You'll need to provide team member emails with `--users=` flag
- Results will be limited to work assigned to specified users

## Installation (If Not Available)

If the `gus-mcp` server is not configured in your environment, you can request setup from:

1. **Your Claude Code Administrator**
   - Ask them to configure the gus-mcp MCP server
   - Reference: Cursor has this server configured successfully

2. **Salesforce Internal Support**
   - File a ticket requesting gus-mcp server access
   - Mention use case: team-wide backlog analysis for nevering

3. **Self-Service (If Applicable)**
   - Check internal Salesforce documentation for gus-mcp server setup
   - May require specific permissions or configuration

## Configuration Details (For Admins)

If you're setting up the gus-mcp server, here's what you need:

### Tool Name
```
mcp__gus-mcp__query_gus_records
```

### Capabilities
- Natural language query interface for GUS records
- Team-scoped work item retrieval
- Support for complex filters and queries

### Example Query
```
"List all backlog work items for team Pardot - Marketing AI and Data Alignment"
```

### Expected Output
- List of work items (W-numbers)
- May write results to a file for large result sets
- Tested with 482 items successfully retrieved

## Testing Your Setup

Once the `gus-mcp` server is configured, test it:

```bash
/rank-backlog "Your Team Name"
```

**Expected output if working:**
```
Analysis Mode: natural-language-query
✓ Used GUS natural language query (gus-mcp server)
✓ Retrieved team-scoped backlog items directly
Found 482 backlog items for team...
```

**If not working (falls back to multi-user mode):**
```
Analysis Mode: multi-user-query
ℹ️ gus-mcp server not available, using fallback mode
Please provide team member emails with --users flag
```

## Workaround (Until gus-mcp is Available)

Use multi-user mode with team member emails:

```bash
/rank-backlog "Your Team" --users=email1@salesforce.com,email2@salesforce.com,email3@salesforce.com
```

**How to get team member emails:**
1. Check team Slack channel → Members list
2. GUS team page → Team Members section
3. Salesforce org chart / People Finder
4. Ask your engineering manager

**Tips:**
- Include all active engineers on the team
- Include tech leads and managers if they have assigned work
- More emails = more complete results

## Comparison

### With gus-mcp Server
```bash
# Simple command
/rank-backlog "Pardot - Marketing AI and Data Alignment"

# Output: 482 items in ~30 seconds
```

### Without gus-mcp Server (Fallback)
```bash
# Complex command with all team member emails
/rank-backlog "Pardot - Marketing AI and Data Alignment" --users=michael.meeks@salesforce.com,avigad.mizrahi@salesforce.com,jason.osborne@salesforce.com,nir.tzavchon@salesforce.com,john.doe@salesforce.com

# Output: Only items assigned to those 5 users, ~2-3 minutes
# May miss unassigned work or work assigned to other team members
```

## Troubleshooting

### "Server gus-mcp not found" Error
**Cause:** The gus-mcp server is not configured in your environment

**Solution:**
1. Use multi-user mode as workaround (see above)
2. Request gus-mcp server setup from your admin
3. Continue using fallback mode until configured

### Natural Language Query Returns No Results
**Cause:** Query syntax may not be recognized

**Try these alternatives:**
- "Show me all open bugs and user stories for team {name} in backlog"
- "Get backlog items for team {name} with status New, Triaged, In Progress, Waiting"
- "Find work items in backlog for {name}"

### Permission Denied
**Cause:** Your account may not have access to gus-mcp server

**Solution:**
1. Check with your admin about gus-mcp permissions
2. Verify your GUS access level
3. Use multi-user mode with your own email as workaround

## Benefits Summary

### Why Request gus-mcp Server Setup?

1. **Comprehensive Results**: Get ALL team backlog items, not just assigned work
2. **Simplicity**: No need to manage team member email lists
3. **Speed**: Single query vs. multiple user queries
4. **Accuracy**: True team-scoped analysis for nevering decisions
5. **Maintainability**: One command, no updates needed when team changes

### Business Case

"The gus-mcp server enables accurate backlog cleanup analysis by providing team-scoped queries. This allows us to identify 400+ nevering candidates quickly, reducing technical debt and improving sprint planning. Without it, we're limited to partial analysis of only assigned work, potentially missing significant cleanup opportunities."

## References

- **Proof of Concept**: Cursor successfully retrieved 482 backlog items using gus-mcp
- **Team**: Pardot - Marketing AI and Data Alignment
- **Date Tested**: 2026-02-26
- **Tool Used**: `mcp__gus-mcp__query_gus_records`

## Questions?

Contact:
- Your Claude Code administrator
- Salesforce Internal Tools support
- #claude-code Slack channel (internal)

---

*This guide is part of the rank-backlog skill v2.0.0*
