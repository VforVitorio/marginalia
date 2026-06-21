/**
 * Typed API client for marginalia backend.
 *
 * All calls go to /api (Vite dev proxy → :8000; production served directly
 * from FastAPI on :8000). No base-URL config needed.
 *
 * Error contract: the backend returns { "detail": "..." } with the relevant
 * HTTP status. apiFetch throws ApiError on non-2xx responses.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export interface Settings {
  vault_path: string;
  scan_folder: string;
  active_provider: string | null;
  active_model: string | null;
  strategies: string[];
}

export interface ProviderInfo {
  id: string;
  display_name: string;
  kind: "local" | "cloud";
  current_model: string | null;
  models: string[];
}

export interface ProvidersResponse {
  providers: ProviderInfo[];
  active: string | null;
  claude_authenticated: boolean;
}

export interface ScannedPdf {
  rel_path: string;
  name: string;
}

export interface ScanResponse {
  pdfs: ScannedPdf[];
}

export interface JobCreated {
  job_id: string;
  name: string;
  pages: number;
}

export interface PageState {
  index: number;
  image_url: string;
  markdown: string;
  done: boolean;
}

export interface JobState {
  job_id: string;
  name: string;
  status: "pending" | "running" | "done" | "error";
  pages: PageState[];
}

export interface ExportResult {
  written: string[];
}

export interface SelectProviderRequest {
  provider_id: string;
  model?: string;
}

export interface ExportRequest {
  vault_path: string;
  strategies: string[];
}

// ── Error class ──────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Core fetch helper ────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      headers: { "Content-Type": "application/json", ...init?.headers },
      ...init,
    });
  } catch (err) {
    throw new ApiError(0, "Cannot reach the backend — is it running?");
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // ignore parse errors — keep the HTTP status message
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content → return undefined cast
  if (response.status === 204) return undefined as unknown as T;

  return response.json() as Promise<T>;
}

// ── Settings ─────────────────────────────────────────────────────────────────

export async function getSettings(): Promise<Settings> {
  return apiFetch<Settings>("/settings");
}

export async function updateSettings(partial: Partial<Settings>): Promise<Settings> {
  return apiFetch<Settings>("/settings", {
    method: "PUT",
    body: JSON.stringify(partial),
  });
}

// ── Providers ─────────────────────────────────────────────────────────────────

export async function getProviders(): Promise<ProvidersResponse> {
  return apiFetch<ProvidersResponse>("/providers");
}

export async function selectProvider(req: SelectProviderRequest): Promise<Settings> {
  return apiFetch<Settings>("/providers/select", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// ── Scan ─────────────────────────────────────────────────────────────────────

export async function scanFolder(): Promise<ScanResponse> {
  return apiFetch<ScanResponse>("/scan");
}

// ── Jobs ─────────────────────────────────────────────────────────────────────

/**
 * POST /api/jobs as multipart/form-data. Do NOT set Content-Type — fetch sets it
 * with the correct boundary. The backend accepts either a `file` or a `rel_path`
 * form field.
 */
async function postJobForm(form: FormData): Promise<JobCreated> {
  let response: Response;
  try {
    response = await fetch("/api/jobs", { method: "POST", body: form });
  } catch {
    throw new ApiError(0, "Cannot reach the backend — is it running?");
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // ignore parse errors — keep the HTTP status message
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<JobCreated>;
}

/** Create a job from a file upload (drag-and-drop / file picker). */
export async function createJobFromFile(file: File): Promise<JobCreated> {
  const form = new FormData();
  form.append("file", file);
  return postJobForm(form);
}

/** Create a job from a scanned PDF (rel_path returned by GET /api/scan). */
export async function createJobFromScan(relPath: string): Promise<JobCreated> {
  const form = new FormData();
  form.append("rel_path", relPath);
  return postJobForm(form);
}

export async function getJob(jobId: string): Promise<JobState> {
  return apiFetch<JobState>(`/jobs/${jobId}`);
}

export async function updatePageMarkdown(
  jobId: string,
  pageIndex: number,
  markdown: string,
): Promise<void> {
  return apiFetch<void>(`/jobs/${jobId}/pages/${pageIndex}`, {
    method: "PUT",
    body: JSON.stringify({ markdown }),
  });
}

export async function exportJob(
  jobId: string,
  req: ExportRequest,
): Promise<ExportResult> {
  return apiFetch<ExportResult>(`/jobs/${jobId}/export`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/** URL for a page image (used directly in <img src> — not a fetch call). */
export function pageImageUrl(jobId: string, pageIndex: number): string {
  return `/api/jobs/${jobId}/pages/${pageIndex}/image`;
}
