# Moirai User Guide: Getting Started

Welcome to Moirai! This guide will walk you through using Moirai as an end user to manage your press review and stay on top of industry trends.

## What is Moirai?

Moirai is a **GenAI-powered press review platform** that helps you:
- 📰 **Aggregate news** from multiple RSS feeds into one place
- 🤖 **Synthesize articles** into actionable Events and Trends using AI
- 📊 **Track patterns** across articles to identify emerging topics
- 💬 **Ask questions** about your feed with an integrated chat interface

Think of it as an AI assistant that reads hundreds of articles and distills them into what matters to you.

---

## Getting Started: First 5 Minutes

### 1. Log In
Open Moirai in your browser (ask your admin for the URL). You'll see a login screen.
- **Username & Password:** Provided by your admin

### 2. Explore the Dashboard
Once logged in, you'll see **4 columns**:

```
┌─────────────┬──────────────┬──────────────┬──────────────┐
│   FEEDS     │  ARTICLES    │    EVENTS    │    TRENDS    │
├─────────────┼──────────────┼──────────────┼──────────────┤
│ • Tech News │ • Article 1  │ • Issue A    │ • Topic 1    │
│ • Science   │ • Article 2  │ • Issue B    │ • Topic 2    │
│ • Business  │ • Article 3  │ • Issue C    │ • Topic 3    │
└─────────────┴──────────────┴──────────────┴──────────────┘
```

- **FEEDS:** RSS feeds you're subscribed to
- **ARTICLES:** Raw articles from those feeds (newest first)
- **EVENTS:** AI-synthesized "issues" (grouped articles about same topic)
- **TRENDS:** High-level trends emerging across events

---

## Core Workflows

### Workflow 1: Browse & Read Articles

1. **Look at the ARTICLES column** — sorted by most recent
2. **Click an article title** to open it in a side panel
3. **Read the summary** and preview
4. **Click the link** to read the full article (opens in new tab)

**Keyboard shortcut:** Press `n` to jump to the next article.

### Workflow 2: Create an Issue from an Article

Found something important that needs action? Create an **Issue** (Event).

1. **Click the article** you want to create an issue from
2. **Click "Raise Issue"** button in the article detail panel
3. A **chat wizard** will ask you 3 clarifying questions:
   - "What's the key problem or opportunity?"
   - "Who should care about this?"
   - "What action would you suggest?"
4. **Answer each question** (or skip if you prefer)
5. **Submit** — Moirai creates the issue and shows it in the EVENTS column

**Note:** Issues stay visible until you mark them as "Sealed" (resolved/archived).

### Workflow 3: Review AI-Synthesized Events

1. **Look at the EVENTS column** — each Event is a group of related articles
2. **Click an Event** to see all articles in that group
3. **Read the AI summary** of what's happening
4. **Decide:** Is this important? Does it need action?
5. **Options:**
   - ✅ **Keep it** — monitor for more articles
   - 🔒 **Seal it** — mark as resolved/archived (moves to past view)
   - ❓ **Ask questions** — use chat to dig deeper

### Workflow 4: Spot Trends

1. **Look at the TRENDS column** — patterns across all events
2. **Click a Trend** to see which events contributed to it
3. **Use chat** to ask:
   - "What's driving this trend?"
   - "Which companies are mentioned?"
   - "Is this a risk or opportunity?"

---

## Using the Chat Interface

Moirai includes an **AI chat assistant** to help you analyze your press review.

### How to Use Chat

1. **Open chat:** Click the 💬 button in the bottom-right corner
2. **Ask questions** like:
   - "What's happening in AI this week?"
   - "Which articles mention cybersecurity?"
   - "What are the 3 biggest stories right now?"
   - "Tell me about the Goldman Sachs news"

3. **Chat remembers context:** Ask follow-up questions naturally
4. **Copy responses:** Hover over a message and click the copy icon

### Example Chat Session

```
You: "What are the top risks mentioned this week?"
Assistant: Based on 47 articles, the top risks are:
1. Supply chain disruptions (8 mentions)
2. Inflation (12 mentions)
3. Cybersecurity (15 mentions)

You: "Tell me more about cybersecurity"
Assistant: The cybersecurity articles mention:
- New ransomware variants (40% of mentions)
- Cloud misconfiguration (30%)
- AI-powered attacks (30%)
```

---

## Advanced Features

### Filter by Feed

You may have multiple feeds (Tech, Science, Business, etc.). To focus on one:

1. **In the FEEDS column**, click a feed name
2. ARTICLES, EVENTS, and TRENDS will **filter to that feed only**
3. **Click "All Feeds"** to see everything again

### View Your Lifespan Dashboard

Want to see which issues have been long-lived (strategic) vs short-term (tactical)?

1. **Click "Lifespan" tab** (top navigation)
2. **See issues grouped by longevity:**
   - 🏃 **Transient:** 1-3 days (news blips)
   - ⏱️ **Temporal:** 1-2 weeks (short trends)
   - 🏛️ **Epic:** 3+ weeks (strategic themes)

This helps you distinguish important from noise.

### River of News Stream

Click the **"River"** tab to see a different view:
- 📰 **Pure River:** Chronological list of all articles
- ⏰ **Time-Blocked:** Grouped by publish date
- 🤖 **AI-Annotated:** Ranked by AI importance/priority

---

## Tips & Tricks

### 💡 Tip 1: Keyboard Navigation
- `j`/`k` — Move to next/previous article
- `n` — Jump to next unread
- `?` — Show all shortcuts

### 💡 Tip 2: Save Time with Shortcuts
- **Raise Issue** button = instant issue creation without typing
- **Chat context** = click any article, ask chat "What does this mean?"

### 💡 Tip 3: Use Chat for Analysis
Instead of manually reading 20 articles, ask:
- "Summarize the top 5 stories"
- "Which are mentioned most?"
- "What's the sentiment?"

### 💡 Tip 4: Seal Old Issues
Keep your Events column clean by sealing issues that:
- Have been resolved
- Are no longer relevant
- Are archived for later reference

### 💡 Tip 5: Return to Trending Topics
Look at the TRENDS column daily. If a trend stays for >3 days, it's likely important for your business.

---

## Common Questions

### Q: Where do articles come from?
**A:** From RSS feeds your admin configured. Ask your admin to add more feeds if you want to track additional topics.

### Q: Can I customize what I see?
**A:** Yes! Your admin can configure which feeds you have access to, and you can filter by feed in the UI.

### Q: How often is the feed updated?
**A:** Articles are typically fetched every 15-30 minutes. Your admin can adjust this.

### Q: Can I export articles?
**A:** Currently, you can copy-paste from the UI or use the chat to summarize. Ask your admin about bulk export if needed.

### Q: Is my data private?
**A:** Yes! Each user has their own isolated workspace (UUID-scoped). Your issues, feeds, and browsing are not visible to other users.

### Q: How does the AI know what matters?
**A:** The AI synthesizes articles based on:
- Topic clustering (articles about the same thing)
- Recency (recent articles weighted higher)
- Cross-feed frequency (mentioned in multiple feeds)
- Your annotations (if you mark something important)

---

## Next Steps

1. **Subscribe to 2-3 feeds** (ask your admin to set these up)
2. **Spend 10 minutes** browsing articles
3. **Create 1-2 issues** from important articles
4. **Ask the chat** a question about your industry
5. **Check back daily** — Moirai gets better as more articles accumulate

---

## Getting Help

- **Questions about usage?** Ask your admin or your team
- **Want more feeds?** Contact your admin
- **Found a bug?** Report to your admin with a screenshot
- **Have feature ideas?** Suggest them to your admin

---

**Happy reviewing!** 🚀
