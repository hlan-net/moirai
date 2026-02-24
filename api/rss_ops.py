from xml.sax.saxutils import escape


def _generate_category_tags(article):
    """Build category tags for events, trends, and AI annotations."""
    categories = []

    # Events and Trends
    if "events" in article:
        for event_name in article["events"]:
            categories.append(f'    <category domain="event">{escape(event_name)}</category>')

    if "trends" in article:
        for trend_name in article["trends"]:
            categories.append(f'    <category domain="trend">{escape(trend_name)}</category>')

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
        tags.append(f'    <category domain="priority">{escape(str(priority))}</category>')
    
    sentiment = annotations.get("sentiment")
    if sentiment:
        tags.append(f'    <category domain="sentiment">{escape(str(sentiment))}</category>')
    
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
