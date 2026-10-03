import { describe, expect, it } from "vitest";
import type { Job } from "../src/api/types";
import { displayedStatus, isPublishReady } from "../src/api/jobStatus";

describe("publish readiness display", () => {
  const base = {
    status: "READY_FOR_PUBLISH",
    revision: 3,
    artifacts: [],
    review: {
      media_sha256: "reviewed-sha",
      status: "PASS",
      human_confirmed: true,
    },
  } as unknown as Job;
  it("does not display a success without a matching final artifact", () => {
    expect(isPublishReady(base)).toBe(false);
    expect(displayedStatus(base)).toBe("NEEDS_HUMAN");
  });
  it("binds success to revision and the actual reviewed media hash", () => {
    const artifact = {
      kind: "final",
      revision: 3,
      mime_type: "video/mp4",
      sha256: "reviewed-sha",
    };
    expect(isPublishReady({ ...base, artifacts: [artifact] } as Job)).toBe(
      true,
    );
    expect(
      isPublishReady({
        ...base,
        artifacts: [{ ...artifact, revision: 2 }],
      } as Job),
    ).toBe(false);
    expect(
      isPublishReady({
        ...base,
        artifacts: [{ ...artifact, sha256: "different" }],
      } as Job),
    ).toBe(false);
  });
});
