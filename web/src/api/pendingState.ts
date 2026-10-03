import type { RunAction } from "./types";

export function blocksPaidRun(
  action: RunAction,
  hasExistingAudio: boolean,
): boolean {
  return (
    action === "voice" ||
    action === "produce" ||
    (action === "storyboard" && !hasExistingAudio)
  );
}

export function hasUnknownOperation(
  pending: Record<string, unknown> | null,
): boolean {
  if (!pending) return false;
  if (pending.operation_status === "UNKNOWN") return true;
  // Older persisted jobs used a diagnostic code in their issues instead.
  return (
    Array.isArray(pending.issues) &&
    pending.issues.some(
      (issue) => typeof issue === "string" && /\bUNKNOWN\b/.test(issue),
    )
  );
}
