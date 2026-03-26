import { computed, ref, watch, type Ref } from 'vue'

/**
 * Makes an element draggable via pointer events on a handle element.
 *
 * Returns:
 *   - `dragStyle`      — bind as `:style` on the element to move
 *   - `handleProps`    — bind as `v-bind` on the drag-handle element
 *   - `resetPosition`  — call to snap back to (0, 0)
 *
 * Usage:
 *   const { dragStyle, handleProps, resetPosition } = useDraggable(targetRef)
 *
 * The element must have a CSS-defined default position (e.g. right: 0; top: 0).
 * The composable applies `transform: translate(x, y)` on top of that position
 * and clamps so the element stays within the viewport.
 */
function clamp(val: number, min: number, max: number) {
  return Math.min(Math.max(val, min), max)
}

export function useDraggable(
  targetRef: Ref<HTMLElement | null>,
  resetSignal?: Ref<unknown>,
) {
  const translateX = ref(0)
  const translateY = ref(0)

  const dragStyle = computed(() => ({
    transform: `translate(${translateX.value}px, ${translateY.value}px)`,
  }))

  // Drag threshold: minimum pixels moved before starting drag
  // This allows clicks to work properly with Wacom pens and other pointer devices
  const DRAG_THRESHOLD = 5

  let pointerDown = false
  let dragging = false
  let startPointerX = 0
  let startPointerY = 0
  let startTranslateX = 0
  let startTranslateY = 0

  function onPointerDown(e: PointerEvent) {
    if (e.button !== 0) return
    
    // Record pointer down but don't start dragging yet
    pointerDown = true
    dragging = false
    startPointerX = e.clientX
    startPointerY = e.clientY
    startTranslateX = translateX.value
    startTranslateY = translateY.value
    
    // Capture pointer but DON'T preventDefault yet - allow click events
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }

  function onPointerMove(e: PointerEvent) {
    if (!pointerDown || !targetRef.value) return

    const dx = e.clientX - startPointerX
    const dy = e.clientY - startPointerY
    const distance = Math.sqrt(dx * dx + dy * dy)

    // Only start dragging if moved beyond threshold
    if (!dragging && distance > DRAG_THRESHOLD) {
      dragging = true
      // Now prevent default to stop text selection during drag
      e.preventDefault()
    }

    if (!dragging) return

    const rect = targetRef.value.getBoundingClientRect()

    // Compute the element's un-translated position
    const baseLeft = rect.left - translateX.value
    const baseTop = rect.top - translateY.value

    const newX = startTranslateX + dx
    const newY = startTranslateY + dy

    // Clamp: keep the element fully within the viewport
    const minX = -baseLeft                                    // left edge of viewport
    const maxX = window.innerWidth - baseLeft - rect.width   // right edge of viewport
    const minY = -baseTop                                     // top edge of viewport
    const maxY = window.innerHeight - baseTop - rect.height  // bottom edge of viewport

    translateX.value = clamp(newX, minX, maxX)
    translateY.value = clamp(newY, minY, maxY)
  }

  function onPointerUp(e: PointerEvent) {
    if (!pointerDown) return
    
    pointerDown = false
    dragging = false
    
    ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  }

  function resetPosition() {
    translateX.value = 0
    translateY.value = 0
  }

  // Reset position whenever the signal changes (e.g. when the modal opens)
  if (resetSignal) {
    watch(resetSignal, resetPosition)
  }

  const handleProps = {
    onPointerdown: onPointerDown,
    onPointermove: onPointerMove,
    onPointerup: onPointerUp,
    onPointercancel: onPointerUp,
  }

  return { dragStyle, handleProps, resetPosition }
}
