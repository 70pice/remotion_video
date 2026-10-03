import { afterEach, describe, expect, it, vi } from "vitest";
import type { Job } from "../src/api/types";
import { chooseLatestJob } from "../src/api/useJob";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("API restart and progress recovery", () => {
  it("stops after one session recovery attempt if authorization remains rejected", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ csrf_token: "old" }))
      .mockResolvedValueOnce(
        Response.json({ detail: "restart" }, { status: 401 }),
      )
      .mockResolvedValueOnce(Response.json({ csrf_token: "new" }))
      .mockResolvedValueOnce(
        Response.json({ detail: "denied" }, { status: 401 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("../src/api/client");
    await expect(api.jobs()).rejects.toThrow("denied");
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("uses authoritative revisions before wall clock timestamps", () => {
    const current = {
      job_id: "job",
      revision: 1,
      latest_event_id: 10,
      updated_at: "2026-10-03T10:00:00Z",
    } as Job;
    const next = {
      ...current,
      revision: 2,
      latest_event_id: 11,
      updated_at: "2026-10-03T09:59:59Z",
    };
    expect(chooseLatestJob(current, next)).toBe(next);
  });
});
