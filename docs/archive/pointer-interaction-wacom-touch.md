# Pointer Interaction: Wacom, Touch, and Mouse Support

## Overview
Moirai is designed to be a high-productivity dashboard for information synthesis. To support diverse workflows—ranging from traditional desktop setups to creative workstations and mobile devices—the application must handle varied pointer interaction models with high precision.

This document describes the design philosophy and implementation strategy for robust support of Wacom pens, touch interfaces, and standard mouse devices.

## Conceptual Framework
In a complex UI featuring draggable components (like the chat drawer) and interactive data elements, the distinction between a **click/tap** and a **drag** is critical. 

The project's goal is to ensure that:
1. **Accessibility:** Users with specialized input devices (like Wacom tablets) have the same level of control as mouse users.
2. **Intent Detection:** The system correctly distinguishes between intentional movement (dragging) and unintentional micro-movement (clicking with a shaky pen or finger).
3. **Fluidity:** Interactions feel natural and responsive across all device types without requiring device-specific configuration from the user.

## Implementation Principles

### 1. Pointer Event Abstraction
We utilize the modern `PointerEvent` API to unify input handling. This allows a single logic path to handle mouse, touch, and pen inputs while retaining access to device-specific properties (like pressure or tilt) if needed.

### 2. The Drag Threshold
To prevent accidental drags—a common issue with high-sensitivity pens and touch screens—we implement a **5-pixel movement threshold**.
- **Click/Tap:** If the pointer is released within 5 pixels of its starting position, it is treated as a click.
- **Drag:** Only movement exceeding 5 pixels triggers the dragging state.

### 3. Visual Feedback
Regardless of the input device, the UI provides immediate visual cues:
- **Hover States:** Visual changes when a pointer enters interactive zones (primarily for mouse/pen).
- **Active States:** Immediate feedback on pointer-down to acknowledge intent.
- **Cursor Overrides:** Dynamic cursor changes (`grabbing` vs `grab`) to indicate draggable status.

## Use Cases

### Wacom Pen Interaction
Digital analysts often use Wacom tablets for ergonomic or creative reasons. The high sensitivity of these pens can cause standard `click` events to fail if the nib moves even slightly during the tap. Our threshold logic ensures these taps are registered correctly as clicks, enabling seamless use of buttons and text selection within draggable containers.

### Touch & Mobile
On touch devices, dragging and scrolling are primary interactions. By correctly identifying drag intent, we ensure that users can reposition the chat drawer or other layout elements without accidentally triggering actions on the elements they are touching.

### Mouse Precision
Traditional mouse users benefit from the same threshold logic, which prevents accidental "micro-drags" when clicking quickly on interactive items.

## Verification & Testing
Robust pointer support is verified using:
- **Device-Specific Testing:** Manual verification on Wacom Intuos/Cintiq hardware and various touch devices.
- **Pointer Event Simulation:** Automated tests using Playwright/Cypress that simulate pointer movements with varying thresholds to ensure intent detection remains accurate.
