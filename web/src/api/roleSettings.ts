import type {
  RoleId,
  RoleModelConfig,
  RoleModels,
  Settings,
  SettingsPatch,
} from "./types";

export const modelRoles = [
  {
    id: "materials",
    label: "素材",
    description: "检索各平台知识、来源图片和网页截图，给后续文案与导演使用。",
  },
  {
    id: "screenwriter",
    label: "编剧",
    description: "整理主题和事实来源，生成短视频文案。",
  },
  {
    id: "script_reviewer",
    label: "文案审查",
    description: "审查编剧稿件的事实、钩子、逻辑、画面与版权风险。",
  },
  {
    id: "voice",
    label: "配音",
    description: "模型提供语气与发音建议，真实声音仍由字节配音接口生成。",
  },
  {
    id: "director",
    label: "导演",
    description: "根据真实音频时间，规划镜头与画面表达。",
  },
  {
    id: "editing",
    label: "剪辑",
    description: "模型提供节奏与布局建议，视频仍由 Remotion 实际渲染。",
  },
  {
    id: "review",
    label: "审核",
    description: "检查内容与来源风险，最终发布资格仍需规则检查和人工复核。",
  },
] as const satisfies ReadonlyArray<{
  id: RoleId;
  label: string;
  description: string;
}>;

export const doubaoScriptModel = "doubao-seed-2-1-pro-260915";

function defaultRole(role: RoleId): RoleModelConfig {
  if (role === "screenwriter" || role === "script_reviewer") {
    return {
      enabled: true,
      provider: "claude_code_cli",
      model: doubaoScriptModel,
      timeout_seconds: 300,
    };
  }
  return {
    enabled: false,
    provider: "codex_cli",
    model: "",
    timeout_seconds: 300,
  };
}

export function readRoleModels(settings: Settings): RoleModels {
  const roles: RoleModels = {
    materials: defaultRole("materials"),
    screenwriter: defaultRole("screenwriter"),
    script_reviewer: defaultRole("script_reviewer"),
    voice: defaultRole("voice"),
    director: defaultRole("director"),
    editing: defaultRole("editing"),
    review: defaultRole("review"),
  };
  for (const { id } of modelRoles) {
    roles[id] = { ...roles[id], ...settings.role_models?.[id] };
  }
  return roles;
}

// Send only edits so an older settings page cannot overwrite untouched role fields.
export function buildRoleModelsPatch(
  draft: RoleModels,
  saved: RoleModels,
): NonNullable<SettingsPatch["role_models"]> {
  const patch: NonNullable<SettingsPatch["role_models"]> = {};
  for (const { id } of modelRoles) {
    const next = draft[id];
    const previous = saved[id];
    const changes: Partial<RoleModelConfig> = {};
    if (next.enabled !== previous.enabled) changes.enabled = next.enabled;
    if (next.provider !== previous.provider) changes.provider = next.provider;
    if (next.model !== previous.model) changes.model = next.model;
    if (next.timeout_seconds !== previous.timeout_seconds)
      changes.timeout_seconds = next.timeout_seconds;
    if (Object.keys(changes).length) patch[id] = changes;
  }
  return patch;
}
