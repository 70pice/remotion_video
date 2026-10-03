import type { Brief } from "./types";

// Only clear the exact snapshot acknowledged by the save response. A newer edit
// stays visible even if it was dispatched just before the controls were locked.
export function finishBriefSave(
  current: Brief | null,
  submitted: Brief,
): Brief | null {
  return current === submitted ? null : current;
}
