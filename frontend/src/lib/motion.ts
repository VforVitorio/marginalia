/**
 * Shared motion-preference check (WCAG 2.3.3).
 *
 * Single source of truth for "should this component skip its GSAP entrance/exit
 * animations?" — used by every component that hand-rolls GSAP tweens (CSS-only
 * transitions are already neutralised globally, see index.css's
 * `prefers-reduced-motion` media query).
 */

/** True when the user has asked the OS to minimise motion. */
export function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
