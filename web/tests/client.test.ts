import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("authenticated API requests", () => {
  it("reads and refreshes the CLI catalog without altering the selected model ID in settings", async () => {
    const catalog = {
      provider: "codex_cli",
      status: "ready",
      models: [],
      message: "",
      fetched_at: "",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ csrf_token: "token" }))
      .mockResolvedValueOnce(Response.json(catalog))
      .mockResolvedValueOnce(Response.json(catalog))
      .mockResolvedValueOnce(Response.json({}));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("../src/api/client");
    await api.models("codex_cli");
    await api.models("codex_cli", true);
    await api.saveSettings({
      role_models: { director: { model: "future/model:v2" } },
    });
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/session",
      "/api/models/codex_cli",
      "/api/models/codex_cli?refresh=true",
      "/api/settings",
    ]);
    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toEqual({
      role_models: { director: { model: "future/model:v2" } },
    });
  });
  it("binds a human reply to the exact pending token that was displayed", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ csrf_token: "token" }))
      .mockResolvedValueOnce(Response.json({ status: "QUEUED" }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("../src/api/client");
    const job = {
      job_id: "job",
      revision: 4,
      pending_input: { pending_token: "current-question-token" },
    } as unknown as Parameters<typeof api.resume>[0];
    await api.resume(job, "confirm", "已核对", "reply-key");
    const payload = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(payload.pending_token).toBe("current-question-token");
    expect(payload.base_revision).toBe(4);
    expect(payload.idempotency_key).toBe("reply-key");
  });
  it("establishes a session before the first protected read", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ csrf_token: "session-token" }))
      .mockResolvedValueOnce(Response.json([]));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("../src/api/client");
    await expect(api.jobs()).resolves.toEqual([]);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/session",
      "/api/jobs",
    ]);
    expect(fetchMock.mock.calls[1][1].credentials).toBe("include");
  });

  it.each([401, 403])(
    "retries an expired session (%s) only once with the identical command and key",
    async (status) => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(Response.json({ csrf_token: "old-token" }))
        .mockResolvedValueOnce(Response.json({ detail: "expired" }, { status }))
        .mockResolvedValueOnce(Response.json({ csrf_token: "new-token" }))
        .mockResolvedValueOnce(Response.json({ status: "QUEUED" }));
      vi.stubGlobal("fetch", fetchMock);
      const { api } = await import("../src/api/client");
      const job = { job_id: "job-1", revision: 5 } as Parameters<
        typeof api.run
      >[0];
      await api.run(job, "voice", "stable-key");
      const mutations = fetchMock.mock.calls.filter(([url]) =>
        String(url).endsWith("/runs"),
      );
      expect(mutations).toHaveLength(2);
      expect(mutations[0][1].body).toBe(mutations[1][1].body);
      expect(JSON.parse(mutations[1][1].body).idempotency_key).toBe(
        "stable-key",
      );
      expect(mutations[0][1].headers.get("X-CSRF-Token")).toBe("old-token");
      expect(mutations[1][1].headers.get("X-CSRF-Token")).toBe("new-token");
    },
  );

  it("never automatically resubmits a command after an uncertain network failure", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ csrf_token: "token" }))
      .mockRejectedValueOnce(new TypeError("network"));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("../src/api/client");
    const job = { job_id: "job-1", revision: 1 } as Parameters<
      typeof api.run
    >[0];
    await expect(api.run(job, "voice", "one-key")).rejects.toThrow("network");
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/runs")),
    ).toHaveLength(1);
  });

  it("explains draft conflicts without discarding the server detail", async () => {
    const { ApiError, explainError } = await import("../src/api/client");
    expect(explainError(new ApiError(409, "base_revision is stale"))).toContain(
      "刷新任务",
    );
    expect(explainError(new ApiError(409, "base_revision is stale"))).toContain(
      "base_revision is stale",
    );
  });
});
