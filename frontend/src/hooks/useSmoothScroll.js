import { useEffect } from 'react';

/* Inertial scroll for the app's own scroll container.
 *
 * #root has overflow-x: hidden, which forces computed overflow-y to auto, so
 * #root — not the window — is what actually scrolls. Wheel events are
 * intercepted and the container is eased toward an accumulated target instead
 * of jumping by the raw delta, which is what produces the glide.
 *
 * Deliberately skipped on touch (native momentum is already good), under
 * prefers-reduced-motion, and when a modifier is held (pinch/browser zoom).
 * Scrolls the app did not originate — keyboard, scrollbar drag, anchor jumps —
 * resync the target rather than being fought.
 */
export default function useSmoothScroll() {
  useEffect(() => {
    const el = document.getElementById('root');
    if (!el) return undefined;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined;
    if (window.matchMedia('(pointer: coarse)').matches) return undefined;

    let current = el.scrollTop;
    let target = el.scrollTop;
    let frame = 0;
    let animating = false;
    let last = 0;

    const clamp = (value) => {
      const max = Math.max(0, el.scrollHeight - el.clientHeight);
      return Math.min(max, Math.max(0, value));
    };

    const step = (now) => {
      // Clamped so a stall (background tab, long frame) cannot make the
      // container jump the whole remaining distance at once.
      const dt = Math.min(64, now - last);
      last = now;

      const distance = target - current;
      if (Math.abs(distance) < 0.5) {
        current = target;
        el.scrollTop = current;
        animating = false;
        return;
      }
      // Frame-rate independent: the same glide at 60Hz, 120Hz or 144Hz. A plain
      // per-frame factor would move ~2.4x faster on a 144Hz display.
      const ease = 1 - Math.pow(0.89, dt / 16.667);
      current += distance * ease;
      el.scrollTop = current;
      frame = window.requestAnimationFrame(step);
    };

    /* The nearest element between the pointer and #root that is itself
       scrollable in the direction of this gesture.
     *
     * Without this the page is eased on every wheel event, so a wheel over the
     * chat transcript scrolled the whole document instead of the messages. An
     * opt-in attribute is not enough — anything scrollable has to keep working,
     * including components added later. At either end of the inner area it
     * deliberately returns null, so the page takes over again and scroll
     * chaining behaves normally.
     */
    const nestedScroller = (start, deltaY) => {
      let node = start instanceof Element ? start : null;
      while (node && node !== el) {
        const { overflowY } = window.getComputedStyle(node);
        const scrollable = /^(auto|scroll|overlay)$/.test(overflowY)
          && node.scrollHeight > node.clientHeight + 1;
        if (scrollable) {
          const atTop = node.scrollTop <= 0;
          const atBottom = node.scrollTop + node.clientHeight >= node.scrollHeight - 1;
          if ((deltaY < 0 && !atTop) || (deltaY > 0 && !atBottom)) return node;
        }
        node = node.parentElement;
      }
      return null;
    };

    const onWheel = (event) => {
      // Leave pinch-zoom and browser zoom alone.
      if (event.ctrlKey || event.metaKey) return;
      // Explicit opt-out, for areas that manage their own scrolling.
      if (event.target instanceof Element && event.target.closest('[data-native-scroll]')) return;
      // Hand the gesture to whatever nested scroller is under the pointer.
      if (nestedScroller(event.target, event.deltaY)) return;

      event.preventDefault();
      if (!animating) {
        current = el.scrollTop;
        target = el.scrollTop;
      }
      target = clamp(target + event.deltaY);
      if (!animating) {
        animating = true;
        last = window.performance.now();
        frame = window.requestAnimationFrame(step);
      }
    };

    const onScroll = () => {
      const actual = el.scrollTop;
      if (animating) {
        // Our own writes land on `current`, so a larger gap means something
        // else moved the container — keyboard or an anchor jump. Let it win.
        if (Math.abs(actual - current) > 2) {
          window.cancelAnimationFrame(frame);
          animating = false;
          current = actual;
          target = actual;
        }
        return;
      }
      current = actual;
      target = actual;
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    el.addEventListener('scroll', onScroll, { passive: true });

    return () => {
      window.cancelAnimationFrame(frame);
      el.removeEventListener('wheel', onWheel);
      el.removeEventListener('scroll', onScroll);
    };
  }, []);
}
