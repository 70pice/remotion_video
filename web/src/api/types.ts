// Python contracts are the shared definition source. Regenerate, don't duplicate.
import type {
  Alignment as GeneratedAlignment,
  ResumeRequest,
  RunRequest,
} from "../../../contracts/generated/models";
export type {
  Asset,
  Artifact,
  Brief,
  Caption,
  ComponentEntry,
  Finding,
  Job,
  Review,
  Script,
  ScriptSegment,
  Shot,
  Timeline,
} from "../../../contracts/generated/models";

export interface Health {
  status: string;
  worker_alive: boolean;
  version: string;
}
export type RunAction = RunRequest["action"];
export type Decision = ResumeRequest["decision"];
export type Settings = Record<string, unknown>;
export type Alignment = Omit<GeneratedAlignment, "audio_sha256">;
