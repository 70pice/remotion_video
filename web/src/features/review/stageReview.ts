import type { Job } from "../../api/types";

const DEFAULT_MIN_NOTE_LENGTH = 10;
const MIN_TOKEN_LENGTH = 16;
const MAX_NOTE_LENGTH = 3000;

export interface StageReviewPending {
  kind: "stage_review";
  title: string;
  stage: string;
  nodeName: string;
  confirmationRequirements: string[];
  minNoteLength: number;
  pendingToken: string;
  revision: number;
  threadId: string;
  dependencyFingerprint: string;
}

function optionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function numberOrDefault(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : fallback;
}

function clampNoteLength(value: unknown): number {
  const length = numberOrDefault(value, DEFAULT_MIN_NOTE_LENGTH);
  return Math.min(MAX_NOTE_LENGTH, Math.max(0, length));
}

function noteLength(note: string): number {
  return Array.from(note.trim()).length;
}

export function getStageReviewPending(job: Job): StageReviewPending | null {
  const pending = job.pending_input;
  if (!pending || pending.kind !== "stage_review") return null;

  const title = optionalString(pending.title);
  const stage = optionalString(pending.stage);
  const nodeName = optionalString(pending.node_name);
  const pendingToken = optionalString(pending.pending_token);
  const threadId = optionalString(pending.thread_id);
  const dependencyFingerprint = optionalString(pending.dependency_fingerprint);
  const revision = numberOrDefault(pending.revision, NaN);

  if (
    !title ||
    !stage ||
    !nodeName ||
    !pendingToken ||
    !threadId ||
    !dependencyFingerprint ||
    !Number.isFinite(revision)
  )
    return null;

  return {
    kind: "stage_review",
    title,
    stage,
    nodeName,
    confirmationRequirements: stringList(pending.confirmation_requirements),
    minNoteLength: clampNoteLength(pending.min_note_length),
    pendingToken,
    revision,
    threadId,
    dependencyFingerprint,
  };
}

export function stageReviewIdentity(
  pending: StageReviewPending | null,
): string {
  return pending
    ? `${pending.revision}:${pending.pendingToken}:${pending.dependencyFingerprint}`
    : "";
}

export function canConfirmStageReview(
  job: Job,
  pending: StageReviewPending,
  note: string,
  checked: boolean,
): boolean {
  return (
    job.status === "NEEDS_HUMAN" &&
    job.revision === pending.revision &&
    pending.pendingToken.length >= MIN_TOKEN_LENGTH &&
    checked &&
    noteLength(note) >= pending.minNoteLength
  );
}
