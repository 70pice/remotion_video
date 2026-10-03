import { describe, expect, it } from "vitest";
import { blocksPaidRun, hasUnknownOperation } from "../src/api/pendingState";

describe("unconfirmed paid submission display", () => {
  it("blocks paid generation while permitting existing-media storyboard and render actions", () => {
    expect(blocksPaidRun("voice", true)).toBe(true);
    expect(blocksPaidRun("produce", false)).toBe(true);
    expect(blocksPaidRun("storyboard", false)).toBe(true);
    expect(blocksPaidRun("storyboard", true)).toBe(false);
    expect(blocksPaidRun("preview", true)).toBe(false);
    expect(blocksPaidRun("final", true)).toBe(false);
    expect(blocksPaidRun("review", true)).toBe(false);
  });
  it("shows UNKNOWN from an explicit marker even when the explanation is Chinese", () => {
    expect(
      hasUnknownOperation({
        operation_status: "UNKNOWN",
        issues: ["配音服务是否受理尚不明确，请核对原请求"],
      }),
    ).toBe(true);
  });
  it("understands older persisted diagnostic issues but not unrelated text", () => {
    expect(
      hasUnknownOperation({
        issues: ["TTS request UNKNOWN; query the existing request"],
      }),
    ).toBe(true);
    expect(
      hasUnknownOperation({
        operation_status: "COMPLETE",
        note: "UNKNOWN was a previous condition",
      }),
    ).toBe(false);
    expect(hasUnknownOperation(null)).toBe(false);
  });
});
