/**
 * App — root of the marginalia SPA.
 *
 * Owns the three-step flow state machine: Import → Review → Export.
 * Animates step transitions with GSAP (slide + fade). Loads provider and
 * settings data once and passes them down.
 *
 * Theme is managed by ThemeToggle (persisted to localStorage).
 */

import { useEffect, useRef, useState } from "react";
import gsap from "gsap";

import {
  getProvidersStatus,
  getSettings,
  selectProvider,
  type ProviderStatus,
  type Settings,
} from "./api/client";
import { prefersReducedMotion } from "./lib/motion";

import { StepIndicator } from "./components/StepIndicator";
import { ProviderPicker } from "./components/ProviderPicker";
import { ThemeToggle } from "./components/ThemeToggle";
import { OnboardingModal } from "./components/OnboardingModal";

import { Import } from "./steps/Import";
import { Review } from "./steps/Review";
import { Export } from "./steps/Export";

// ── Flow state machine ────────────────────────────────────────────────────────

type Step = "import" | "review" | "export";

const STEP_INDEX: Record<Step, number> = {
  import: 0,
  review: 1,
  export: 2,
};

const STEP_BY_INDEX: Step[] = ["import", "review", "export"];

interface ActiveJob {
  jobId: string;
  name: string;
  pageCount: number;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function App() {
  const [step, setStep] = useState<Step>("import");
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);

  const [status, setStatus] = useState<ProviderStatus[] | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [providersLoading, setProvidersLoading] = useState(true);
  const [providerSelectPending, setProviderSelectPending] = useState(false);
  const [providerSelectError, setProviderSelectError] = useState<string | null>(null);

  // First-run onboarding gate — cleared to false once the user sees it.
  const [showOnboarding, setShowOnboarding] = useState<boolean>(
    () => localStorage.getItem("marginalia.onboarded") !== "1",
  );

  // Ref for the animated step container.
  const stepContainerRef = useRef<HTMLDivElement>(null);

  // ── Bootstrap: load settings + providers ────────────────────────────────

  useEffect(() => {
    // Theme is applied before first paint by the inline script in index.html
    // (FE-17) — nothing to do here.

    // Non-blocking — render the Import step even if backend is down.
    Promise.allSettled([getProvidersStatus(), getSettings()]).then(([prov, sett]) => {
      if (prov.status === "fulfilled") setStatus(prov.value.providers);
      if (sett.status === "fulfilled") setSettings(sett.value);
      setProvidersLoading(false);
    });
  }, []);

  // ── GSAP step transition ─────────────────────────────────────────────────

  function transitionToStep(nextStep: Step) {
    const el = stepContainerRef.current;

    // No container or reduced motion → swap instantly. Still move focus into the
    // new step so keyboard / screen-reader users follow the change (WCAG 2.4.3).
    if (!el || prefersReducedMotion()) {
      setStep(nextStep);
      el?.focus({ preventScroll: true });
      return;
    }

    // Exit current step.
    gsap.to(el, {
      opacity: 0,
      y: nextStep === "import" ? 20 : -20, // back = down, forward = up
      duration: 0.2,
      ease: "power2.in",
      onComplete: () => {
        setStep(nextStep);
        // Move focus into the new step (keyboard / SR users follow the change).
        el.focus({ preventScroll: true });
        // Enter next step.
        gsap.fromTo(
          el,
          { opacity: 0, y: nextStep === "import" ? -20 : 20 },
          { opacity: 1, y: 0, duration: 0.25, ease: "power2.out" },
        );
      },
    });
  }

  // ── Event handlers ───────────────────────────────────────────────────────

  function handleJobCreated(jobId: string, name: string, pageCount: number) {
    setActiveJob({ jobId, name, pageCount });
    transitionToStep("review");
  }

  function handleGoExport() {
    transitionToStep("export");
  }

  function handleBackToReview() {
    transitionToStep("review");
  }

  function handleDone() {
    setActiveJob(null);
    transitionToStep("import");
  }

  // Navigate via the step indicator. A job unlocks all three steps; without one
  // only Import is reachable. Never jump forward past current progress.
  function handleStepClick(index: number) {
    const maxStep = activeJob ? 2 : 0;
    if (index > maxStep) return;
    const target = STEP_BY_INDEX[index];
    if (target && target !== step) transitionToStep(target);
  }

  function handleBackToImport() {
    transitionToStep("import");
  }

  function handleOnboardingClose() {
    localStorage.setItem("marginalia.onboarded", "1");
    setShowOnboarding(false);
  }

  async function refreshProviders() {
    try {
      const fresh = await getProvidersStatus();
      setStatus(fresh.providers);
    } catch {
      // Backend unreachable — keep the last known status.
    }
  }

  /**
   * Selects a provider/model. Tracks a pending flag so ProviderPicker can show a
   * busy state on the row, and never throws — a failure is captured in
   * providerSelectError for the picker to surface instead of becoming an
   * unhandled rejection (this used to await two round-trips with no try/catch
   * and no busy state at all).
   *
   * Returns whether the selection succeeded so the picker only closes its
   * popover on success — on failure it stays open with the error visible.
   */
  async function handleProviderSelect(providerId: string, model?: string): Promise<boolean> {
    setProviderSelectPending(true);
    setProviderSelectError(null);
    try {
      const updated = await selectProvider({ provider_id: providerId, model });
      setSettings(updated);
      await refreshProviders();
      return true;
    } catch (err) {
      setProviderSelectError(err instanceof Error ? err.message : "Could not select the provider.");
      return false;
    } finally {
      setProviderSelectPending(false);
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <>
      {showOnboarding && (
        <OnboardingModal onClose={handleOnboardingClose} />
      )}

      <div className="min-h-screen flex flex-col bg-surface transition-colors duration-300">
        {/* ── Header ──────────────────────────────────────────────────── */}
        <header className="border-b border-default bg-surface sticky top-0 z-30">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 py-2 sm:h-14 sm:py-0 flex flex-wrap items-center gap-x-3 gap-y-2 sm:gap-4">
            {/* Wordmark */}
            <a
              href="/"
              className="order-1 font-serif italic text-xl text-primary tracking-tight select-none flex-shrink-0"
              aria-label="marginalia home"
            >
              marginalia
            </a>

            {/* Step indicator — own row on mobile, centred inline on sm+ */}
            <div className="order-3 sm:order-2 w-full sm:w-auto sm:flex-1 flex justify-center">
              <StepIndicator
                current={STEP_INDEX[step]}
                maxStep={activeJob ? 2 : 0}
                onStepClick={handleStepClick}
              />
            </div>

            {/* Controls */}
            <div className="order-2 sm:order-3 ml-auto sm:ml-0 flex items-center gap-2 flex-shrink-0">
              <ProviderPicker
                status={status}
                active={settings?.active_provider ?? null}
                loading={providersLoading}
                selecting={providerSelectPending}
                selectError={providerSelectError}
                onSelect={handleProviderSelect}
                onRefresh={refreshProviders}
              />

              {/* Guide button — reopens the onboarding modal at any time */}
              <button
                type="button"
                aria-label="Open guide"
                title="Guide"
                className="btn-secondary flex items-center gap-1.5 text-xs px-2.5 py-1.5"
                onClick={() => setShowOnboarding(true)}
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3" />
                  <path
                    d="M6.5 6a1.5 1.5 0 1 1 2.5 1.13C8.5 7.5 8 7.9 8 8.5V9"
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinecap="round"
                  />
                  <circle cx="8" cy="11" r="0.65" fill="currentColor" />
                </svg>
                <span className="hidden sm:inline">Guide</span>
              </button>

              <ThemeToggle />
            </div>
          </div>
        </header>

        {/* ── Main content ─────────────────────────────────────────────── */}
        <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8">
          <div ref={stepContainerRef} tabIndex={-1} className="outline-none">

            {step === "import" && (
              <Import onJobCreated={handleJobCreated} />
            )}

            {step === "review" && activeJob && (
              <Review
                jobId={activeJob.jobId}
                jobName={activeJob.name}
                pageCount={activeJob.pageCount}
                onExport={handleGoExport}
                onBack={handleBackToImport}
              />
            )}

            {step === "export" && activeJob && (
              <Export
                jobId={activeJob.jobId}
                jobName={activeJob.name}
                settings={settings}
                onBack={handleBackToReview}
                onDone={handleDone}
                onSettingsChange={setSettings}
              />
            )}
          </div>
        </main>

        {/* ── Footer ──────────────────────────────────────────────────── */}
        <footer className="border-t border-default py-4 text-center">
          <p className="text-2xs text-muted">
            marginalia — Kindle Scribe → Obsidian
          </p>
        </footer>
      </div>
    </>
  );
}
