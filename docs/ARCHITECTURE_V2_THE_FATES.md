# Moirai Architecture: The 2nd iteration (The Hourglass and the Fates)

## 1. Philosophical Overview: The Signal and the Sand
Moirai 2nd iteration moves away from static, hardcoded abstractions like "Events" and "Trends." Instead, it views the flow of information as a constant stream of change—sand falling through an **Hourglass (Tiimalasi)**.

The system is designed to observe this constant change and allow **Issues** to emerge, be measured, and eventually pass into the record of history.

### 1.1 The Sand (Articles)
Articles are the fundamental grains of sand. Individually, they are **Messages** indicating a moment of change. Collectively, their movement reveals the **Signal**. They are transient by nature and exist to be woven into something greater.

### 1.2 Emergent Issues
An **Issue** is the fundamental "thing" that emerges from the sand. It is a **Deduction** made by observing the signal. It is an artifact in the analog sense: a pattern that becomes visible only through the interaction of the signal and the Fates.

Issues are defined by their **Longevity Scale**:

*   **Transient Issues:** High-frequency bursts. They appear suddenly as a flash in the signal and fade just as fast.
*   **Temporal Issues:** Mid-frequency sustained structures. They represent a coherent movement or debate that persists across time.
*   **Epic Issues:** Low-frequency, foundational arcs. These are the standing waves of history, defining the character of a userspace for eternity.

## 2. The Roles of the Moirai

### 2.1 Clotho (The Spinner) - Inception
Clotho identifies the moment a new pattern begins to "issue" from the sand. She **Forges** the initial Issue, identifying the first threads of the signal that move in harmony.
*   **Technical Implementation:** Pattern matching, initial clustering, and the creation of records in the `issues` database.

### 2.2 Lachesis (The Allotter) - Measurement
Lachesis determines the weight and amplitude of each Issue. She "measures" how much of the signal is dedicated to the Issue and assigns its **Longevity Scale**. An Issue can evolve; a transient spark can grow into an epic flame.
*   **Technical Implementation:** Scoring algorithms, importance weighting, and dynamic re-classification.

### 2.3 Atropos (The Inflexible) - Finality
Atropos determines when an Issue has "passed." She does not delete; she cuts the Issue's connection to the active flow of sand. When an Issue is no longer being modulated by new messages, it moves from **Time** (The thing that IS) to **Eternity** (The thing that WAS).
*   **Technical Implementation:** State management (`status: active` vs `status: eternal`). Once eternal, an Issue is an immutable record of the past.

## 3. Data Model Refactor

### 3.1 Unified Issue Storage (The `issues` DB)
The `events` and `trends` databases are merged into a single **`issues`** database.

**Issue Schema:**
```json
{
  "_id": "uuid",
  "logos": "The headline/essence of the deduction",
  "description": "text",
  "userspace": "guid",
  "longevity": "transient | temporal | epic",
  "status": "active | eternal",
  "premises": [
    { "type": "message | issue", "id": "uuid" }
  ],
  "born_at": "timestamp",
  "passed_at": "timestamp | null"
}
```

## 4. MCP & UI Evolution
*   **Tools:** `forge_issue`, `measure_issue`, `seal_issue`, `list_issues`.
*   **UI:** A **Lifespan View** that visualizes the "frequency" of the current userspace, showing how the fast-moving sand crystallizes into the "Things that ARE" and the "Things that WERE."
