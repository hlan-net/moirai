# Moirai User Guide: Getting Started

Welcome to **Moirai**, a press review platform that gathers RSS feeds into one stream of news.

## What is Moirai?

Moirai fetches the feeds its administrator has added, files every article into a section and annotates it with an LLM (topics, priority, sentiment). You read the result on one page, the **Stream**.

The UI has three views: Stream, Login and Settings. Earlier versions also had a dashboard, chat, a lifespan view and agent pages. Those were removed from the UI in 0.12.0; their functions return as parts of the Stream page.

## The Stream page

Open Moirai. The Stream page is the front page.

- **Articles** are listed newest first. A click on a headline opens the article at its source.
- **Sections:** the page opens on Top stories. The menu button (☰) next to Refresh chooses the sections: Top stories, Sports, Culture, Business, one or several at once. With none ticked you get the whole stream. The sections in effect are named next to the article count.
- **View:** in the same menu, Compact or Expanded rows, and grouping By feed or By time.
- **Dots** at the end of a compact row show an article's priority and sentiment, and the events and trends it belongs to. Hover or focus them for details.
- **Refresh:** the page checks for new articles every two minutes and shows their number on the Refresh button. The list changes only when you press it.
- **RSS:** "RSS for this view" in the menu is a feed of the sections you have chosen, for any RSS reader.
- **Your choice of sections** is kept in the page's address and in your browser, so it survives a reload, and the address can be shared.

## Logging in and Settings

Reading the stream may be open to everyone or need a login, depending on how your Moirai is set up. Settings always needs a login.

- **User Settings:** theme and your LLM endpoint.
- **Feeds** (administrators): add, import (a list of URLs or an OPML file), rename, delete and refresh feeds, and choose each feed's section.
- **System Settings** (administrators): system configuration, the model catalog, backup and restore.

## Common questions

**Where do articles come from?** From the RSS feeds listed in Settings → Feeds.

**How often is the stream updated?** The feeds are fetched on a schedule set by the administrator (every 10 minutes by default).

**Why did an article move out of Top stories?** Its section can come from the feed, from its address or from the annotation. The annotation arrives a few seconds after the article, and may move it to Sports, Culture or Business.

**How long are articles kept?** 30 days by default (`ARTICLE_EXPIRATION_DAYS`).

## Getting help

Ask your administrator, or see the [Admin Guide](./tutorial-admin.md) and the [project repository](https://github.com/hlan-net/moirai).
