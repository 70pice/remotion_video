// Python contracts are the shared definition source. Regenerate, don't duplicate.
import type {
  Alignment as GeneratedAlignment,
  ResumeRequest,
  RoleModelConfig,
  RoleModels,
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
  ModelCatalog,
  ModelChoice,
  Review,
  RoleModelConfig,
  RoleModels,
  Script,
  ScriptSegment,
  SettingsPatch,
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
export type RoleId = keyof RoleModels;
export type ModelProvider = RoleModelConfig["provider"];
export interface Settings extends Record<string, unknown> {
  role_models?: Partial<RoleModels>;
  cli_availability?: Partial<Record<ModelProvider, { available: boolean }>>;
}
export type Alignment = Omit<GeneratedAlignment, "audio_sha256">;
