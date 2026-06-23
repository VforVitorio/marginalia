/**
 * OnboardingModal — first-run 3-step introduction modal.
 *
 * Gated by `localStorage.getItem("marginalia.onboarded") === "1"`.
 * Explains: what marginalia is → pick an OCR model → import a notebook.
 *
 * Responsibilities:
 * - Render a centred card over a dimmed backdrop.
 * - Advance through 3 steps with Back / Next / Done buttons + a Skip link.
 * - Animate in via GSAP on mount; animate out before calling `onClose`.
 * - Trap focus inside the modal and close on Esc.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import gsap from "gsap";

// ── Step data ────────────────────────────────────────────────────────────────

interface StepContent {
  title: string;
  body: React.ReactNode;
}

const STEPS: StepContent[] = [
  {
    title: "What is marginalia?",
    body: (
      <div className="space-y-3">
        <p className="text-secondary text-sm leading-relaxed">
          <strong className="text-primary">marginalia</strong> turns your handwritten
          Kindle Scribe notebooks into Markdown notes ready for Obsidian — no
          cloud subscription required unless you want one.
        </p>
        <ul className="space-y-2 text-sm text-secondary">
          <StepBullet icon={<DocIcon />}>
            Drop a single PDF, or point marginalia at your Scribe sync folder
            and pick a notebook — the folder structure becomes your Obsidian
            layout automatically.
          </StepBullet>
          <StepBullet icon={<PenIcon />}>
            A local or cloud OCR model reads each handwritten page and drafts
            Markdown — nothing leaves your machine unless you choose a cloud
            provider.
          </StepBullet>
          <StepBullet icon={<EyeIcon />}>
            You review the draft side-by-side with the original image and edit
            any mistakes before exporting.
          </StepBullet>
          <StepBullet icon={<FolderIcon />}>
            Export writes Markdown files into your Obsidian vault, mirroring
            the source folder hierarchy.
          </StepBullet>
        </ul>
      </div>
    ),
  },
  {
    title: "Pick your OCR model",
    body: (
      <div className="space-y-3">
        <p className="text-secondary text-sm leading-relaxed">
          marginalia supports two provider types. Pick the one that fits your
          privacy and quality needs — you can switch at any time.
        </p>
        <div className="grid gap-2">
          <OptionCard
            label="Local (private)"
            description="Qwen3-VL via Ollama or LM Studio — runs entirely on your machine. Start Ollama/LM Studio, load a model there, then select it here."
            badge="Privacy first"
          />
          <OptionCard
            label="Cloud"
            description="Claude (Anthropic subscription) or Gemini (free-tier key) — highest accuracy on messy handwriting. Requires an internet connection and your credentials."
            badge="Best quality"
          />
        </div>
        <p className="text-xs text-muted pt-1">
          Switch providers any time from the{" "}
          <span className="font-medium text-accent">provider picker</span> in
          the header. A model must be loaded and selected before OCR can start.
        </p>
      </div>
    ),
  },
  {
    title: "Import your first notebook",
    body: (
      <div className="space-y-3">
        <p className="text-secondary text-sm leading-relaxed">
          You're ready. Here's the three-step flow:
        </p>
        <ol className="space-y-2 text-sm">
          <NumberedBullet n={1} label="Import">
            Drag a loose PDF onto the Import panel (you pick the destination
            on export), or use the <em>Scribe folder</em> tab to point
            marginalia at the folder your Kindle Scribe syncs to — its
            sub-folders will become your Obsidian structure automatically.
          </NumberedBullet>
          <NumberedBullet n={2} label="Review">
            Each page shows the original image on the left and the OCR draft
            on the right. Edit any mistakes directly in the text before
            moving on.
          </NumberedBullet>
          <NumberedBullet n={3} label="Export">
            Choose your Obsidian vault path, confirm the folder layout, and
            export. marginalia writes one Markdown file per notebook page.
          </NumberedBullet>
        </ol>
      </div>
    ),
  },
];

// ── Small presentational helpers ─────────────────────────────────────────────

function StepBullet({
  icon,
  children,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-start gap-3">
      <span
        className="flex-shrink-0 mt-0.5 w-7 h-7 rounded-lg flex items-center justify-center text-accent"
        style={{ background: "color-mix(in srgb, var(--color-accent) 12%, transparent)" }}
      >
        {icon}
      </span>
      <span className="leading-relaxed">{children}</span>
    </li>
  );
}

// ── Line icons (16px, currentColor) ──────────────────────────────────────────

function DocIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M4 2h5l3 3v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <path d="M9 2v3h3" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  );
}

function PenIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M10.5 2.5l3 3L6 13l-3.5.5L3 10l7.5-7.5z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <path d="M9 4l3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <circle cx="8" cy="8" r="1.8" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function FolderIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M2 4.5A1.5 1.5 0 0 1 3.5 3h2.2c.4 0 .78.16 1.06.44L8 4.5h4.5A1.5 1.5 0 0 1 14 6v6a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V4.5z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function OptionCard({
  label,
  description,
  badge,
}: {
  label: string;
  description: string;
  badge: string;
}) {
  return (
    <div className="card flex items-start gap-3 py-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-primary">{label}</span>
          <span
            className="text-2xs font-medium px-1.5 py-0.5 rounded-full"
            style={{
              background: "color-mix(in srgb, var(--color-accent) 15%, transparent)",
              color: "var(--color-accent)",
            }}
          >
            {badge}
          </span>
        </div>
        <p className="text-xs text-secondary mt-0.5 leading-relaxed">
          {description}
        </p>
      </div>
    </div>
  );
}

function NumberedBullet({
  n,
  label,
  children,
}: {
  n: number;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-start gap-3">
      <span
        className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold text-surface"
        style={{ background: "var(--color-accent)" }}
      >
        {n}
      </span>
      <div>
        <span className="font-semibold text-primary">{label} — </span>
        <span className="text-secondary">{children}</span>
      </div>
    </li>
  );
}

// ── Step dot indicator ───────────────────────────────────────────────────────

function StepDots({
  total,
  current,
}: {
  total: number;
  current: number;
}) {
  return (
    <div className="flex items-center gap-1.5" aria-hidden="true">
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className="block rounded-full transition-all duration-300"
          style={{
            width: i === current ? "1.5rem" : "0.4rem",
            height: "0.4rem",
            background:
              i === current
                ? "var(--color-accent)"
                : i < current
                  ? "color-mix(in srgb, var(--color-accent) 50%, transparent)"
                  : "var(--color-border-strong)",
          }}
        />
      ))}
    </div>
  );
}

// ── Focus trap ───────────────────────────────────────────────────────────────

/** Returns all focusable elements within a container. */
function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((el) => !el.hasAttribute("disabled"));
}

// ── Modal ────────────────────────────────────────────────────────────────────

interface OnboardingModalProps {
  /** Called after the close animation completes. */
  onClose: () => void;
}

export function OnboardingModal({ onClose }: OnboardingModalProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const backdropRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const firstFocusRef = useRef<HTMLButtonElement>(null);
  const totalSteps = STEPS.length;
  const isLast = stepIndex === totalSteps - 1;

  // ── Entrance animation ───────────────────────────────────────────────────

  useEffect(() => {
    const backdrop = backdropRef.current;
    const card = cardRef.current;
    if (!backdrop || !card) return;

    gsap.fromTo(backdrop, { opacity: 0 }, { opacity: 1, duration: 0.22, ease: "power2.out" });
    gsap.fromTo(
      card,
      { opacity: 0, y: 18, scale: 0.97 },
      { opacity: 1, y: 0, scale: 1, duration: 0.28, ease: "power2.out" },
    );

    // Place focus on the first focusable element.
    firstFocusRef.current?.focus();
  }, []);

  // ── Exit animation, then close ───────────────────────────────────────────

  const closeWithAnimation = useCallback(() => {
    const backdrop = backdropRef.current;
    const card = cardRef.current;
    if (!backdrop || !card) {
      onClose();
      return;
    }
    gsap.to(card, { opacity: 0, y: 12, scale: 0.97, duration: 0.18, ease: "power2.in" });
    gsap.to(backdrop, {
      opacity: 0,
      duration: 0.2,
      ease: "power2.in",
      onComplete: onClose,
    });
  }, [onClose]);

  // ── Esc closes ──────────────────────────────────────────────────────────

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeWithAnimation();
      if (e.key === "Tab") trapFocus(e);
    }

    function trapFocus(e: KeyboardEvent) {
      const card = cardRef.current;
      if (!card) return;
      const focusable = getFocusable(card);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [closeWithAnimation]);

  // ── Step content transition ──────────────────────────────────────────────

  function goToStep(next: number, direction: "forward" | "back") {
    const card = cardRef.current;
    if (!card) {
      setStepIndex(next);
      return;
    }
    const bodyEl = card.querySelector<HTMLElement>(".onboarding-body");
    if (!bodyEl) {
      setStepIndex(next);
      return;
    }
    const exitY = direction === "forward" ? -12 : 12;
    const enterY = direction === "forward" ? 12 : -12;
    gsap.to(bodyEl, {
      opacity: 0,
      y: exitY,
      duration: 0.15,
      ease: "power2.in",
      onComplete: () => {
        setStepIndex(next);
        gsap.fromTo(
          bodyEl,
          { opacity: 0, y: enterY },
          { opacity: 1, y: 0, duration: 0.2, ease: "power2.out" },
        );
      },
    });
  }

  function handleNext() {
    if (isLast) {
      closeWithAnimation();
    } else {
      goToStep(stepIndex + 1, "forward");
    }
  }

  function handleBack() {
    if (stepIndex > 0) goToStep(stepIndex - 1, "back");
  }

  const step = STEPS[stepIndex];

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div
      ref={backdropRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{
        background: "rgba(10,9,8,0.40)",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
      }}
      /* Clicking the backdrop closes the modal. */
      onMouseDown={(e) => {
        if (e.target === backdropRef.current) closeWithAnimation();
      }}
    >
      <div
        ref={cardRef}
        className="relative w-full max-w-md rounded-2xl flex flex-col gap-6 p-7"
        style={{
          // Acrylic / frosted glass: translucent surface + blur, subtle border, top sheen.
          background: "color-mix(in srgb, var(--color-surface) 72%, transparent)",
          backdropFilter: "blur(22px) saturate(150%)",
          WebkitBackdropFilter: "blur(22px) saturate(150%)",
          border: "1px solid color-mix(in srgb, var(--color-border-strong) 55%, transparent)",
          boxShadow: "0 16px 48px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.20)",
        }}
      >
        {/* ── Header ───────────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium text-muted uppercase tracking-widest mb-1">
              Step {stepIndex + 1} of {totalSteps}
            </p>
            <h2
              id="onboarding-title"
              className="font-serif italic text-xl text-primary leading-snug"
            >
              {step?.title}
            </h2>
          </div>

          {/* Close (×) button */}
          <button
            ref={firstFocusRef}
            type="button"
            aria-label="Close introduction"
            className="btn-ghost w-8 h-8 p-0 flex-shrink-0 flex items-center justify-center rounded-lg"
            onClick={closeWithAnimation}
          >
            <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
              <path
                d="M3 3l10 10M13 3L3 13"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>

        {/* ── Body (animated on step change) ───────────────────────── */}
        <div className="onboarding-body min-h-[11rem]">{step?.body}</div>

        {/* ── Footer ───────────────────────────────────────────────── */}
        <div className="flex items-center justify-between gap-4 pt-1">
          {/* Step dots + Skip */}
          <div className="flex items-center gap-3">
            <StepDots total={totalSteps} current={stepIndex} />
            <button
              type="button"
              className="text-xs text-muted hover:text-secondary transition-colors underline underline-offset-2"
              onClick={closeWithAnimation}
            >
              Skip
            </button>
          </div>

          {/* Back / Next / Done */}
          <div className="flex items-center gap-2">
            {stepIndex > 0 && (
              <button type="button" className="btn-secondary text-xs px-3 py-1.5" onClick={handleBack}>
                Back
              </button>
            )}
            <button type="button" className="btn-primary text-xs px-4 py-1.5" onClick={handleNext}>
              {isLast ? "Done" : "Next →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
