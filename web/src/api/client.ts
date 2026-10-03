import type {
  Alignment,
  Asset,
  Brief,
  ComponentEntry,
  Decision,
  Health,
  Job,
  RunAction,
  Script,
  Settings,
  SettingsPatch,
  Timeline,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let sessionToken: Promise<string> | null = null;
function getSessionToken(): Promise<string> {
  sessionToken ??= fetch("/api/session", { credentials: "include" })
    .then(async (response) => {
      if (!response.ok)
        throw new ApiError(response.status, "无法建立本机会话，请刷新页面。");
      const session = (await response.json()) as { csrf_token: string };
      return session.csrf_token;
    })
    .catch((error: unknown) => {
      sessionToken = null;
      throw error;
    });
  return sessionToken;
}

// fetch uses the same origin in development (Vite proxy) and production.
async function request<T>(
  path: string,
  init: RequestInit = {},
  retried = false,
): Promise<T> {
  const bootstrap = getSessionToken();
  const token = await bootstrap;
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (init.method && init.method !== "GET") headers.set("X-CSRF-Token", token);
  const response = await fetch(`/api${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  // A rejected session has no accepted command. Retry once with the original payload/key.
  if ([401, 403].includes(response.status) && !retried) {
    if (sessionToken === bootstrap) sessionToken = null;
    return request<T>(path, init, true);
  }
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail))
        message = body.detail
          .map((item: { msg?: string }) => item.msg ?? "数据格式不正确")
          .join("；");
    } catch {
      /* Keep the HTTP status if the server response isn't JSON. */
    }
    if ([401, 403].includes(response.status) && sessionToken === bootstrap)
      sessionToken = null;
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

export function explainError(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return `任务版本或待回复的问题已经变化。请刷新任务后再操作，避免覆盖新版本。${error.message}`;
  }
  if (error instanceof TypeError)
    return "暂时无法连接服务。请检查服务是否已启动；后台任务状态将在重连后恢复。";
  return error instanceof Error ? error.message : "操作未完成，请重试。";
}

export function newCommandKey(): string {
  return crypto.randomUUID();
}

export const api = {
  health: () => request<Health>("/health"),
  jobs: () => request<Job[]>("/jobs"),
  job: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}`),
  createJob: (brief: Brief) =>
    request<Job>("/jobs", { method: "POST", body: JSON.stringify(brief) }),
  saveDraft: (
    id: string,
    baseRevision: number,
    changes: { brief?: Brief; script?: Script; timeline?: Timeline },
  ) =>
    request<Job>(`/jobs/${encodeURIComponent(id)}/draft`, {
      method: "PATCH",
      body: JSON.stringify({ base_revision: baseRevision, ...changes }),
    }),
  run: (job: Job, action: RunAction, key: string) =>
    request<Job>(`/jobs/${encodeURIComponent(job.job_id)}/runs`, {
      method: "POST",
      body: JSON.stringify({
        base_revision: job.revision,
        action,
        idempotency_key: key,
      }),
    }),
  resume: (job: Job, decision: Decision, note: string, key: string) => {
    const token = job.pending_input?.pending_token;
    if (typeof token !== "string" || !token)
      return Promise.reject(
        new ApiError(409, "当前任务没有可回复的待确认事项。"),
      );
    return request<Job>(`/jobs/${encodeURIComponent(job.job_id)}/resume`, {
      method: "POST",
      body: JSON.stringify({
        base_revision: job.revision,
        decision,
        note,
        idempotency_key: key,
        pending_token: token,
      }),
    });
  },
  cancel: (id: string) =>
    request<Job>(`/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  upload: (id: string, data: FormData) =>
    request<Asset>(`/jobs/${encodeURIComponent(id)}/assets`, {
      method: "POST",
      body: data,
    }),
  saveAlignment: (job: Job, assetId: string, alignment: Alignment) =>
    request<Job>(`/jobs/${encodeURIComponent(job.job_id)}/alignment`, {
      method: "POST",
      body: JSON.stringify({
        base_revision: job.revision,
        asset_id: assetId,
        alignment,
      }),
    }),
  alignment: (jobId: string, assetId?: string) =>
    request<{
      asset_id: string | null;
      alignment: Alignment | null;
      duration_seconds: number | null;
    }>(
      `/jobs/${encodeURIComponent(jobId)}/alignment${assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ""}`,
    ),
  catalog: () => request<ComponentEntry[]>("/catalog"),
  settings: () => request<Settings>("/settings"),
  saveSettings: (settings: SettingsPatch) =>
    request<Settings>("/settings", {
      method: "PATCH",
      body: JSON.stringify(settings),
    }),
};
