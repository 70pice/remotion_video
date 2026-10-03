import { describe, expect, it } from "vitest";
import type { Job } from "../src/api/types";
import { chooseLatestJob } from "../src/api/useJob";

const job = (revision: number, eventId: number): Job =>
  ({
    job_id: "job",
    revision,
    latest_event_id: eventId,
    updated_at: "2026-10-03T00:00:00Z",
  }) as Job;
describe("persisted job polling order", () => {
  it("does not overwrite a mutation with an older revision at the same timestamp", () => {
    const current = job(3, 20);
    expect(chooseLatestJob(current, job(2, 19))).toBe(current);
  });
  it("does not regress event progress within one revision", () => {
    const current = job(3, 22);
    expect(chooseLatestJob(current, job(3, 21))).toBe(current);
    expect(chooseLatestJob(current, job(3, 23)).latest_event_id).toBe(23);
  });
});
