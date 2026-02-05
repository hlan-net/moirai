# Moirai UI Style Guide

This guide outlines the styling conventions, component patterns, and theming guidelines for the Moirai frontend. Follow these standards to ensure a consistent and high-quality user experience across the application.

## 1. Tech Stack & Core Concepts

-   **Framework:** Vue 3 + TypeScript + Vite
-   **Styling:** Native CSS with CSS Variables for theming.
-   **Theming:** First-class support for Dark Mode (default) and Light Mode.
-   **Icons:** Inline SVGs (`fill="currentColor"`) for optimal performance and theme adaptability.

## 2. Theming & Colors

Always use the defined CSS variables instead of hardcoded hex values. This ensures Dark/Light mode compatibility.

| Variable | Usage | Dark Mode (Default) | Light Mode |
| :--- | :--- | :--- | :--- |
| `--bg-color` | Page background | `#242424` | `#ffffff` |
| `--text-color` | Primary text | `rgba(255, 255, 255, 0.87)` | `#213547` |
| `--card-bg` | Content cards/columns | `#242424` | `#ffffff` |
| `--border-color` | Borders, dividers | `#444` | `#ccc` |
| `--primary-color` | Links, accents, focus | `#a8b3cf` | `#007acc` |
| `--button-bg` | Button backgrounds | `#1a1a1a` | `#f9f9f9` |
| `--input-bg` | Input fields | `#333` | `#ffffff` |
| `--input-text` | Input text | `#fff` | `#333` |

### CSS Usage Example
```css
.my-component {
  background-color: var(--card-bg);
  color: var(--text-color);
  border: 1px solid var(--border-color);
}
```

## 3. Component Patterns

### 3.1 Buttons

We use a harmonized set of button styles across the application.

#### Header Action Buttons (`.action-btn`)
Used in column headers or page toolbars (e.g., "Refresh", "Import", "Download").
*   **Style:** Bordered, transparent background, icon + text.
*   **Hover:** `var(--button-bg)` with `var(--primary-color)` border/text.

```html
<button class="action-btn">
  <svg>...</svg>
  Action Name
</button>
```

#### Icon Buttons (`.icon-btn`)
Used for item-level actions (e.g., Delete, Edit, Link).
*   **Style:** Icon only, transparent background, no border.
*   **Hover:** `var(--button-bg)` background, opacity 1.
*   **Variants:** `.delete` (red hover).

```html
<button class="icon-btn" title="Edit">
  <svg>...</svg>
</button>
```

### 3.2 Cards & Columns

*   **Columns:** Use the `.column` class.
    ```css
    .column {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: 4px;
    }
    ```
*   **Items:** List items (e.g., feeds, articles) should use a bottom border.
    ```css
    .item {
      border-bottom: 1px solid var(--border-color);
    }
    ```

### 3.3 Icons

Use inline SVGs.
*   **Size:** Standard is `width="16" height="16"` (viewBox `0 0 24 24`).
*   **Color:** Use `fill="currentColor"` to inherit text color.

```html
<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
  <path d="..." />
</svg>
```

### 3.4 Modals

*   **Overlay:** `.modal-overlay` with `rgba(0, 0, 0, 0.7)`.
*   **Content:** `.modal-content` with `var(--bg-color)` and `var(--text-color)`.

## 4. Best Practices

1.  **Scoped Styles:** Always use `<style scoped>` in Vue components.
2.  **Semantic HTML:** Use `<button>` for actions, `<a>` for navigation.
3.  **Accessibility:** Add `title` attributes to icon-only buttons.
4.  **Composition API:** Use `<script setup lang="ts">`.
