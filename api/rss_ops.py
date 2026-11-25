from xml.sax.saxutils import escape, quoteattr

# Namespace of Moirai's own attributes in /api/stream.rss (prefix ``moirai``).
MOIRAI_RSS_NS = "https://github.com/hlan-net/moirai/ns/rss"


def _generate_category_tags(article):
    """Build category tags for the section, events, trends, and AI annotations."""
    categories = []

    # Stream section (#266): main | sports | culture | business
    section = article.get("section")
    if section:
        categories.append(
            f'    <category domain="section">{escape(str(section))}</category>'
        )

    # Events and Trends: the issues the article is a premise of, attached by
    # enrich_articles_with_issues(). Each carries the issue id in a namespaced
    # attribute, so the Stream page can open the issue (#376).
    for issue in article.get("issues") or []:
        logos = issue.get("logos")
        if not logos:
            continue
        domain = (
            "event" if issue.get("longevity", "transient") == "transient" else "trend"
        )
        issue_id = issue.get("id")
        id_attr = f" moirai:id={quoteattr(str(issue_id))}" if issue_id else ""
        categories.append(
            f'    <category domain="{domain}"{id_attr}>{escape(str(logos))}</category>'
        )

    # AI annotations
    annotations = article.get("annotations")
    if isinstance(annotations, dict):
        categories.extend(_generate_annotation_tags(annotations))

    return "\n".join(categories) if categories else ""


def _generate_annotation_tags(annotations):
    """Helper to build XML for AI annotations."""
    tags = []
    for topic in annotations.get("topics", []):
        tags.append(f'    <category domain="topic">{escape(str(topic))}</category>')

    priority = annotations.get("priority")
    if priority:
        tags.append(
            f'    <category domain="priority">{escape(str(priority))}</category>'
        )

    sentiment = annotations.get("sentiment")
    if sentiment:
        tags.append(
            f'    <category domain="sentiment">{escape(str(sentiment))}</category>'
        )

    return tags


def generate_rss_item_xml(article, feed_title_map, parse_datetime_func):
    """
    Generate the XML string for a single RSS item.
    """
    title = escape(article.get("title", "Untitled"))
    link = escape(article.get("link", ""))
    summary = escape(article.get("summary", ""))
    published = article.get("published", "")

    # Convert ISO datetime to RFC 822 format for RSS
    pub_date = ""
    if published:
        try:
            dt = parse_datetime_func(published)
            pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S %z")
        except Exception:
            pass

    category_xml = _generate_category_tags(article)

    # Add source feed info
    feed_url = article.get("feed_url", "")
    feed_title = feed_title_map.get(feed_url, "Unknown Source")
    source_xml = (
        f"    <source><title>{escape(feed_title)}</title></source>"
        if feed_title
        else ""
    )

    item_xml = f"""  <item>
    <title>{title}</title>
    <link>{link}</link>
    <description>{summary}</description>
    <pubDate>{pub_date}</pubDate>
    <guid isPermaLink="true">{link}</guid>
{category_xml}
{source_xml}
  </item>"""

    return item_xml
