# Moirai Feature Roadmap: Aggregated Stream Improvements

The following features aim to improve the "Aggregated Stream" browsing experience, focusing on high-density information flow and stable chronological discovery (inspired by the "River of News" style).

## High-Density Discovery (River of News Style)

### [ ] Feature Proposal 1: The "Pure River" (High-Density List)
Focus on extreme information density and readability, mimicking `river.hlan.net`.
* **Visuals:** 
    - Remove card borders and background colors for individual items. 
    - Use thin lines to separate articles. 
    - Group articles by feed only if they appear sequentially in the timeline.
* **Stability:** New articles are prepended to the top but do *not* automatically shift the view while reading.
* **Notification:** A "New Articles Available" toast appears at the top, allowing the user to click to scroll up when ready.

### [ ] Feature Proposal 2: The "Time-Blocked" River
Group articles by temporal windows rather than sources to maintain strict chronological flow.
* **Structure:** Sections labeled "Last Hour", "Earlier Today", "Yesterday".
* **Visuals:** 
    - Minimalist headlines by default. 
    - Summary hidden/collapsed and only expands on click/hover. 
    - Source favicon and name appear as a small tag next to the title.
* **Stability:** Once a "Time Block" is rendered, its contents never change order.

### [ ] Feature Proposal 3: The "AI-Annotated River" (Contextual Scan)
Strictly chronological flow with AI-driven speed-reading markers.
* **Structure:** Single chronological list of headlines.
* **Visuals:** 
    - Color-coded dots or small badges next to titles indicating **Topic**, **Priority**, or **Sentiment**.
    - E.g., Green for "Tech", Blue for "Climate", Red for "Urgent/Breaking".
* **Stability:** Items stay exactly where they were first fetched.
* **Benefit:** Allows users to scan the stream quickly and only stop for specific interest markers.
