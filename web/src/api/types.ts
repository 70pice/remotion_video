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
  ScriptCritique,
  ScriptCritiqueIssue,
  ScriptDiscussion,
  ScriptDiscussionRound,
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
  voice_api_key_configured?: boolean;
  voice_access_token_configured?: boolean;
  voice_configured?: boolean;
  role_models?: Partial<RoleModels>;
  cli_availability?: Partial<Record<ModelProvider, { available: boolean }>>;
  research_skills?: Array<{ name: string; path: string; installed: boolean; detail: string }>;
  research_tools?: Array<{
    id: string;
    label: string;
    status: string;
    detail: string;
    kind?: string;
    notes?: string;
  }>;
}
export type Alignment = Omit<GeneratedAlignment, "audio_sha256">;
