# Moirai Documentation

Welcome to Moirai's documentation! Choose your role below to get started.

## 📚 Tutorials by Role

### 🧑‍💼 [User Guide](./TUTORIAL_USER.md)
**For journalists, analysts, and content reviewers using Moirai**

Learn how to:
- Browse and manage RSS feeds
- Create issues from articles
- Use AI-powered chat to ask questions
- Track trends and patterns
- Manage your workspace

**Time to read:** 10-15 minutes
**Get started:** [→ User Guide](./TUTORIAL_USER.md)

---

### 🔧 [Admin Guide](./TUTORIAL_ADMIN.md)
**For IT admins and system operators deploying and maintaining Moirai**

Learn how to:
- Deploy Moirai (Docker or local)
- Create users and manage credentials
- Configure RSS feeds
- Set up AI agents for automation
- Monitor system health
- Backup and scale

**Time to read:** 20-30 minutes
**Get started:** [→ Admin Guide](./TUTORIAL_ADMIN.md)

---

### 👨‍💻 [Developer Guide](./TUTORIAL_DEVELOPER.md)
**For software engineers building and extending Moirai**

Learn how to:
- Set up development environment
- Understand the architecture
- Add custom API endpoints
- Create MCP tools
- Write custom agent logic
- Write tests and contribute

**Time to read:** 30-45 minutes
**Get started:** [→ Developer Guide](./TUTORIAL_DEVELOPER.md)

---

## 🏗️ Architecture Overview

Moirai is a **GenAI-native press review platform** with three main layers:

```
┌─────────────────────────────────────────────┐
│        Vue.js 3 Frontend (port 3000)       │
│  (Dashboard, feeds, chat, trends)           │
└─────────────────────────────────────────────┘
                        ↕
┌─────────────────────────────────────────────┐
│      Flask REST API (port 8088)             │
│  (/api/articles, /api/issues, /api/chat)   │
└─────────────────────────────────────────────┘
                        ↕
┌─────────────────────────────────────────────┐
│    CouchDB + Redis + MCP Server            │
│  (Storage, caching, agent orchestration)   │
└─────────────────────────────────────────────┘
```

**Data flows:**
1. **Ingestion:** Feeds → Articles → Annotations (via LLM)
2. **Synthesis:** Articles → Events → Trends (via agents)
3. **Interaction:** Users query via chat, create issues, browse

---

## 🚀 Quick Start by Role

### User: I want to find important news
```
1. Log in to http://localhost:3000
2. Browse ARTICLES column
3. Click "Raise Issue" for important stories
4. Check TRENDS column for patterns
5. Ask chat questions anytime
```

### Admin: I want to deploy Moirai
```
1. Read Admin Guide Part 1 (Deployment)
2. Run: docker compose up -d
3. Set up feeds via Admin UI
4. Create users and configure agents
5. Monitor via Prometheus (port 9000)
```

### Developer: I want to add a feature
```
1. Read Developer Guide Part 1 (Setup)
2. Clone repo and run dev servers
3. Write feature + tests
4. Submit PR with clear description
5. Follow code style in CLAUDE.md
```

---

## 📖 Documentation Files

| Document | Purpose | Audience |
|----------|---------|----------|
| [TUTORIAL_USER.md](./TUTORIAL_USER.md) | How to use Moirai | End users, analysts |
| [TUTORIAL_ADMIN.md](./TUTORIAL_ADMIN.md) | How to deploy & manage | IT admins, ops |
| [TUTORIAL_DEVELOPER.md](./TUTORIAL_DEVELOPER.md) | How to extend Moirai | Engineers, contributors |
| [../CLAUDE.md](../CLAUDE.md) | Architecture & conventions | Developers, maintainers |
| [../README.md](../README.md) | Project overview | Everyone |

---

## 🆘 Getting Help

| Question | Answer |
|----------|--------|
| **How do I use Moirai?** | See [User Guide](./TUTORIAL_USER.md) |
| **How do I deploy Moirai?** | See [Admin Guide](./TUTORIAL_ADMIN.md) Part 1 |
| **How do I add a feature?** | See [Developer Guide](./TUTORIAL_DEVELOPER.md) |
| **What's the API reference?** | See [../README.md](../README.md#api) (coming soon) |
| **Where's the architecture doc?** | See [../CLAUDE.md](../CLAUDE.md) |
| **Found a bug?** | Open a GitHub Issue with logs |
| **Want to contribute?** | See [Developer Guide](./TUTORIAL_DEVELOPER.md) Part 9 |

---

## 🔄 Learning Path

### For Users
1. [User Guide](./TUTORIAL_USER.md) (15 min)
2. Create your first issue (5 min)
3. Ask the chat a question (5 min)
4. Explore the Lifespan view (5 min)
5. **Done!** You're ready to use Moirai

### For Admins
1. [Admin Guide](./TUTORIAL_ADMIN.md) Part 1 (Deployment) (15 min)
2. Deploy Moirai (10 min)
3. [Admin Guide](./TUTORIAL_ADMIN.md) Part 2 (Users & Feeds) (10 min)
4. Create feeds and users (10 min)
5. [Admin Guide](./TUTORIAL_ADMIN.md) Part 3 (Agents) (10 min)
6. Configure agents (10 min)
7. **Done!** Your Moirai is ready for users

### For Developers
1. [Developer Guide](./TUTORIAL_DEVELOPER.md) Part 1 (Setup) (15 min)
2. Set up dev environment (15 min)
3. [Developer Guide](./TUTORIAL_DEVELOPER.md) Part 2 (Architecture) (10 min)
4. Read [../CLAUDE.md](../CLAUDE.md) (10 min)
5. [Developer Guide](./TUTORIAL_DEVELOPER.md) Part 4 (Common Tasks) (20 min)
6. Write and test a feature (30 min)
7. Submit a PR (5 min)
8. **Done!** You're a Moirai contributor

---

## 📊 Feature Matrix

| Feature | User | Admin | Developer |
|---------|------|-------|-----------|
| Browse feeds | ✅ | ✅ | ✅ |
| Create issues | ✅ | ✅ | ✅ |
| Use chat | ✅ | ✅ | ✅ |
| View trends | ✅ | ✅ | ✅ |
| Add feeds | ❌ | ✅ | ✅ |
| Create users | ❌ | ✅ | ❌ |
| Configure agents | ❌ | ✅ | ✅ |
| View metrics | ❌ | ✅ | ✅ |
| Add API endpoints | ❌ | ❌ | ✅ |
| Create MCP tools | ❌ | ❌ | ✅ |
| Write agent logic | ❌ | ❌ | ✅ |

---

## 💡 Tips for Each Role

### For Users
- **Use chat frequently** — it's your best friend for analysis
- **Seal old issues** — keeps your view clean
- **Check trends daily** — emerging patterns are gold
- **Save time** — use "Raise Issue" button instead of manual notes

### For Admins
- **Monitor metrics** — Prometheus shows system health
- **Add diverse feeds** — breadth improves trend detection
- **Test agents carefully** — they run continuously
- **Back up regularly** — CouchDB has valuable data

### For Developers
- **Follow CLAUDE.md** — it's the source of truth for architecture
- **Write tests first** — TDD keeps code quality high
- **Isolate by userspace** — security depends on it
- **Use changes feed** — not polling, for efficiency

---

## 🎯 Common Goals

### Goal: I want to track a specific industry
**Solution:** Add 3-4 RSS feeds from that industry (Admin)

### Goal: I want AI to automatically categorize articles
**Solution:** Create a custom agent logic function (Developer) + configure it as ON_NEW_ARTICLE trigger (Admin)

### Goal: I want to export articles to another tool
**Solution:** Use the chat to summarize, or build a custom API endpoint (Developer)

### Goal: I want to train the AI on our preferences
**Solution:** Mark articles as important/low-priority, AI learns from patterns (User)

---

## 📝 Conventions

All tutorials follow these conventions:

- **Code blocks** show real examples you can copy
- **Terminal commands** start with `$` or `#`
- **File paths** are relative to repository root
- **Emphasis** highlights important concepts
- **Links** go to relevant sections or external docs

---

## 🔐 Security Notes

- **Userspace isolation** keeps data private (multiple users won't see each other's data)
- **Authentication required** for all API endpoints
- **HTTPS recommended** for production (use reverse proxy)
- **Default passwords must change** before going live
- **API tokens expire** — rotate them regularly

---

## 📅 Version Info

- **Latest Version:** v0.6.0
- **Python:** 3.10+
- **Node.js:** 18+
- **CouchDB:** 3.2+
- **Redis:** 6.0+

For changelog, see [../CHANGELOG.md](../CHANGELOG.md)

---

## 🤝 Contributing

Found a typo in the docs? Want to improve a tutorial?

1. Fork the repository
2. Edit the `.md` file
3. Submit a pull request
4. We'll review and merge!

See [Developer Guide Part 9](./TUTORIAL_DEVELOPER.md#part-9-contributing-guidelines) for details.

---

**Start with the tutorial for your role above!** 👆

Questions? Check the relevant tutorial or open a GitHub Issue.
