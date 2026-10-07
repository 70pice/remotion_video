import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { api, explainError } from "../api/client";
import {
  catalogModelChoice,
  customModelChoice,
  defaultModelChoice,
  formatModelCacheTime,
  modelFromChoice,
  selectedModelChoice,
} from "../api/modelChoices";
import {
  buildRoleModelsPatch,
  modelRoles,
  readRoleModels,
} from "../api/roleSettings";
import type {
  ModelCatalog,
  RoleId,
  Settings,
  SettingsPatch,
} from "../api/types";
import { Notice, PageHeading } from "../components/ui";

const defaultVoiceModel = "seed-tts-2.0-expressive";
const voiceModelSuggestions = [
  {
    value: "seed-tts-2.0-expressive",
    label: "Expressive：支持自然语言表演指导",
  },
  { value: "seed-tts-2.0-standard", label: "Standard：普通合成，不支持情绪指导" },
];
const defaultVoiceStyle =
  "像真正理解内容的人在给朋友讲一个值得关注的新发现，不要播音腔、朗诵腔或逐字念稿。" +
  "开头带克制的好奇，问题句自然上扬；解释段放松、清楚，给长句留出呼吸；" +
  "遇到转折和反常识信息时先收一下，再加重真正关键的内容；结论坚定收住。" +
  "不要字字加重，不要全程兴奋，也不要一口气读完。";
const customVoiceStylePreset = "custom";
const voiceStylePresets = [
  {
    id: "natural",
    label: "自然",
    style: defaultVoiceStyle,
  },
  {
    id: "speech",
    label: "演讲（情感丰富）",
    style:
      "像现场演讲一样表达：情绪饱满，关键观点明显加重，转折处放慢，结尾有感染力。",
  },
  {
    id: "enthusiastic",
    label: "热情",
    style:
      "保持热情和兴奋感，语气明亮，重点词上扬，节奏略快但吐字清楚。",
  },
  {
    id: "serious",
    label: "严肃",
    style:
      "语气沉稳克制，降低夸张起伏，重点信息清晰有力，保留自然停顿。",
  },
];
const voiceSpeedSuggestions = ["0.5", "0.8", "1.0", "1.2", "1.3", "1.4", "1.6", "2.0"];

interface FieldLabel {
  label: string;
  placeholder?: string;
  secret?: boolean;
  configured?: string;
}
type Field = FieldLabel &
  (
    | {
        key: keyof Pick<
          SettingsPatch,
          | "max_llm_calls"
          | "research_results_per_platform"
          | "research_max_searches"
          | "research_max_sources"
          | "research_max_visuals"
          | "max_voice_chars"
          | "render_timeout_seconds"
        >;
        type: "number";
      }
    | {
        key: keyof Pick<
          SettingsPatch,
          | "voice_endpoint"
          | "voice_app_id"
          | "voice_resource_id"
          | "voice_id"
          | "voice_model"
          | "voice_access_token"
          | "voice_api_key"
          | "ark_api_key"
          | "search_api_key"
          | "google_search_engine_id"
          | "aligner_url"
          | "aligner_api_key"
        >;
        type?: "url";
      }
  );
const sections: { title: string; description: string; fields: Field[] }[] = [
  {
    title: "文案模型认证",
    description: "Claude Code CLI 调用豆包 Pro 2.1 时使用火山方舟密钥。",
    fields: [
      {
        key: "ark_api_key",
        label: "火山方舟 API Key",
        secret: true,
        configured: "ark_api_key_configured",
      },
    ],
  },
  {
    title: "你的声音",
    description: "接入你提供的字节接口和复刻音色。",
    fields: [
      { key: "voice_endpoint", label: "配音接口地址", type: "url" },
      { key: "voice_app_id", label: "应用 ID" },
      {
        key: "voice_resource_id",
        label: "资源 ID（新版声音复刻）",
        placeholder: "seed-icl-2.0（按账号实际资源填写）",
      },
      { key: "voice_id", label: "音色 ID" },
      { key: "voice_model", label: "语音合成模型" },
      {
        key: "voice_access_token",
        label: "访问令牌",
        secret: true,
        configured: "voice_access_token_configured",
      },
      {
        key: "voice_api_key",
        label: "新鉴权 API Key（按你的接口填写）",
        secret: true,
        configured: "voice_api_key_configured",
      },
    ],
  },
  {
    title: "检索与时间对齐",
    description: "检索提供事实来源，对齐提供音频的真实词句时间。",
    fields: [
      {
        key: "search_api_key",
        label: "检索密钥",
        secret: true,
        configured: "search_configured",
      },
      { key: "google_search_engine_id", label: "Google CSE 搜索引擎 ID" },
      { key: "aligner_url", label: "时间对齐服务地址", type: "url" },
      {
        key: "aligner_api_key",
        label: "对齐服务密钥",
        secret: true,
        configured: "aligner_configured",
      },
    ],
  },
  {
    title: "运行限额",
    description: "控制每条视频的调用与渲染上限。",
    fields: [
      { key: "max_llm_calls", label: "模型调用次数上限", type: "number" },
      {
        key: "research_results_per_platform",
        label: "每个平台结果数",
        type: "number",
      },
      { key: "research_max_searches", label: "素材检索调用上限", type: "number" },
      { key: "research_max_sources", label: "来源读取上限", type: "number" },
      { key: "research_max_visuals", label: "图片/截图采集尝试上限", type: "number" },
      { key: "max_voice_chars", label: "配音字数上限", type: "number" },
      {
        key: "render_timeout_seconds",
        label: "单次渲染超时（秒）",
        type: "number",
      },
    ],
  },
];

export function voiceProviderPatch(
  provider: NonNullable<SettingsPatch["voice_provider"]>,
): Pick<
  SettingsPatch,
  "voice_provider" | "voice_endpoint" | "voice_style" | "voice_speech_rate"
> {
  if (provider === "byte_ws") {
    return {
      voice_provider: provider,
      voice_endpoint: "wss://openspeech.bytedance.com/api/v3/tts/bidirection",
    };
  }
  if (provider === "byte_http") {
    return {
      voice_provider: provider,
      voice_endpoint:
        "https://openspeech.bytedance.com/api/v3/tts/unidirectional",
      voice_style: "",
      voice_speech_rate: 0,
    };
  }
  return { voice_provider: provider };
}

function showVoiceField(key: string, provider: unknown): boolean {
  if (key === "voice_model") return provider === "byte_ws";
  return (
    provider !== "byte_ws" ||
    !["voice_app_id", "voice_access_token"].includes(key)
  );
}

function discussionMaxRounds(settings: Settings): number {
  const value = settings.script_discussion_max_rounds;
  return typeof value === "number" && Number.isFinite(value) ? value : 1;
}

function clampDiscussionRounds(value: number): number {
  if (!Number.isFinite(value)) return 1;
  return Math.min(5, Math.max(1, Math.round(value)));
}

function clampVoiceSpeechRate(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(-50, Math.round(value)));
}

function speechRateToMultiplier(value: unknown): string {
  const multiplier = 1 + clampVoiceSpeechRate(value) / 100;
  return Number(multiplier.toFixed(2)).toString();
}

function speechRateFromMultiplier(value: unknown, fallback: unknown): number {
  const parsed =
    typeof value === "string" && value.trim() !== ""
      ? Number(value)
      : typeof value === "number"
        ? value
        : Number.NaN;
  if (!Number.isFinite(parsed)) return clampVoiceSpeechRate(fallback);
  return clampVoiceSpeechRate(Math.round((parsed - 1) * 100));
}

function voiceSpeedMultiplierValue(values: Settings): string {
  const draft = values.voice_speed_multiplier;
  if (typeof draft === "string") return draft;
  if (typeof draft === "number" && Number.isFinite(draft)) return String(draft);
  return speechRateToMultiplier(values.voice_speech_rate);
}

function voiceStyleValue(values: Settings): string {
  return typeof values.voice_style === "string"
    ? values.voice_style.slice(0, 2000)
    : "";
}

function selectedVoiceStylePreset(values: Settings): string {
  const draftPreset = values.voice_style_preset;
  if (
    typeof draftPreset === "string" &&
    (draftPreset === customVoiceStylePreset ||
      voiceStylePresets.some((preset) => preset.id === draftPreset))
  )
    return draftPreset;
  const style = voiceStyleValue(values);
  return (
    voiceStylePresets.find((preset) => preset.style === style)?.id ??
    customVoiceStylePreset
  );
}

export function createSettingsPayload(
  values: Settings,
  saved: Settings,
): SettingsPatch {
  const payload: SettingsPatch = {};
  for (const section of sections) {
    for (const field of section.fields) {
      if (!showVoiceField(field.key, values.voice_provider)) continue;
      const value =
        values[field.key] ??
        (field.key === "voice_model" ? defaultVoiceModel : undefined);
      if (field.secret && !value) continue; // Blank preserves the configured secret.
      if (field.type === "number") {
        if (typeof value === "number") payload[field.key] = value;
      } else if (typeof value === "string") {
        payload[field.key] = value;
      }
    }
  }
  if (
    values.voice_provider === "none" ||
    values.voice_provider === "byte_http" ||
    values.voice_provider === "byte_ws"
  )
    payload.voice_provider = values.voice_provider;
  if (values.voice_provider === "byte_ws") {
    payload.voice_style = voiceStyleValue(values);
    payload.voice_speech_rate = speechRateFromMultiplier(
      values.voice_speed_multiplier,
      values.voice_speech_rate,
    );
  }
  if (values.voice_provider === "byte_http") {
    payload.voice_style = "";
    payload.voice_speech_rate = 0;
  }
  if (
    values.search_provider === "none" ||
    values.search_provider === "opencli_google" ||
    values.search_provider === "tavily" ||
    values.search_provider === "google_cse"
  )
    payload.search_provider = values.search_provider;
  if (typeof values.capture_enabled === "boolean")
    payload.capture_enabled = values.capture_enabled;
  if (typeof values.research_download_images === "boolean")
    payload.research_download_images = values.research_download_images;
  if (Array.isArray(values.research_platforms))
    payload.research_platforms = values.research_platforms.filter(
      (item): item is string => typeof item === "string",
    );
  const roles = buildRoleModelsPatch(
    readRoleModels(values),
    readRoleModels(saved),
  );
  if (Object.keys(roles).length) payload.role_models = roles;
  if (
    typeof values.script_discussion_max_rounds === "number" &&
    values.script_discussion_max_rounds !==
      saved.script_discussion_max_rounds
  )
    payload.script_discussion_max_rounds = clampDiscussionRounds(
      values.script_discussion_max_rounds,
    );
  return payload;
}

interface SettingsFormProps {
  saved: Settings;
  values: Settings;
  busy: boolean;
  modelCatalog?: ModelCatalog;
  traeModelCatalog?: ModelCatalog;
  catalogLoading?: boolean;
  traeCatalogLoading?: boolean;
  catalogError?: string;
  traeCatalogError?: string;
  onRefreshModels?: () => void;
  onRefreshTraeModels?: () => void;
  onChange: (key: string, value: unknown) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

interface CatalogStatusProps {
  label: string;
  refreshLabel: string;
  description: string;
  catalog?: ModelCatalog;
  loading: boolean;
  error: string;
  busy: boolean;
  onRefresh?: () => void;
}

function CatalogStatus({
  label,
  refreshLabel,
  description,
  catalog,
  loading,
  error,
  busy,
  onRefresh,
}: CatalogStatusProps) {
  return (
    <div
      className="model-catalog-status"
      aria-live="polite"
      aria-busy={loading}
    >
      <div className="inline-spread">
        <strong>{label} 本机模型列表</strong>
        {onRefresh && (
          <button
            type="button"
            className="button secondary small"
            aria-label={`刷新 ${refreshLabel} 模型列表`}
            disabled={loading || busy}
            onClick={onRefresh}
          >
            {loading ? "正在读取…" : "刷新模型列表"}
          </button>
        )}
      </div>
      <p className="muted small">
        {loading
          ? "正在读取模型列表；仍可编辑角色配置。"
          : catalog?.status === "ready"
            ? `已读取 ${catalog.models.length} 个模型${catalog.models.some((entry) => entry.hidden) ? "，含隐藏项" : ""}。`
            : "目录尚不可用，可选择 CLI 默认模型或填写自定义模型 ID。"}
      </p>
      <p className="muted small">{description}</p>
      {catalog?.fetched_at && (
        <p className="muted small">
          列表时间（本地）：
          <time dateTime={catalog.fetched_at}>
            {formatModelCacheTime(catalog.fetched_at)}
          </time>
        </p>
      )}
      {error ? (
        <p className="catalog-error">
          {error}
          {catalog?.status === "ready" && " 当前保留上次读取的列表。"}
          角色配置保持不变，可继续使用默认或自定义模型。
        </p>
      ) : catalog?.message ? (
        <p className="muted small">{catalog.message}</p>
      ) : null}
    </div>
  );
}

export function SettingsForm({
  saved,
  values,
  busy,
  modelCatalog,
  traeModelCatalog,
  catalogLoading = false,
  traeCatalogLoading = false,
  catalogError = "",
  traeCatalogError = "",
  onRefreshModels,
  onRefreshTraeModels,
  onChange,
  onSubmit,
}: SettingsFormProps) {
  const roles = readRoleModels(values);
  const [customRoles, setCustomRoles] = useState<
    Partial<Record<RoleId, boolean>>
  >({});
  const codexCatalog =
    modelCatalog?.provider === "codex_cli" ? modelCatalog : undefined;
  const traeCatalog =
    traeModelCatalog?.provider === "trae_cli" ? traeModelCatalog : undefined;
  return (
    <form onSubmit={onSubmit} aria-busy={busy}>
      <fieldset className="editor-fieldset" disabled={busy}>
        <div className="settings-section-heading">
          <h2>七个角色的模型</h2>
          <p className="muted small">
            各角色独立选择本机 CLI 和模型。留空模型名称时使用该 CLI 的默认模型。
            检测只确认是否安装；运行前请在本机完成相应 CLI 登录。
            仅影响后续实际调用；已有文案、分镜和产物不会自动重做。
          </p>
        </div>
        <CatalogStatus
          label="Codex CLI"
          refreshLabel="Codex"
          description="向项目实际使用的 Codex CLI 查询模型，查询失败时回退到本机缓存。可选列表不代表当前账号权限，实际支持以 CLI 调用为准。"
          catalog={codexCatalog}
          loading={catalogLoading}
          error={catalogError}
          busy={busy}
          onRefresh={onRefreshModels}
        />
        <CatalogStatus
          label="TRAE CLI"
          refreshLabel="TRAE"
          description="向项目实际使用的 TRAE CLI 查询模型列表。可选列表不代表当前账号权限，实际支持以 CLI 调用为准。"
          catalog={traeCatalog}
          loading={traeCatalogLoading}
          error={traeCatalogError}
          busy={busy}
          onRefresh={onRefreshTraeModels}
        />
        <div className="settings-grid role-model-grid">
          {modelRoles.map((role) => {
            const config = roles[role.id];
            const availability = saved.cli_availability?.[config.provider];
            const providerLabel =
              config.provider === "codex_cli"
                ? "Codex CLI"
                : config.provider === "trae_cli"
                  ? "TRAE CLI"
                  : "Claude Code CLI";
            const roleCatalog =
              config.provider === "codex_cli"
                ? codexCatalog
                : config.provider === "trae_cli"
                  ? traeCatalog
                  : undefined;
            const updateRole = (changes: Partial<typeof config>) => {
              onChange("role_models", {
                ...roles,
                [role.id]: { ...config, ...changes },
              });
            };
            const statusId = `role-cli-status-${role.id}`;
            const choice = selectedModelChoice(
              config.model,
              roleCatalog,
              customRoles[role.id],
            );
            const selectedEntry = roleCatalog?.models.find(
              (entry) => entry.id === config.model,
            );
            return (
              <section
                className="panel form-panel role-model-card"
                key={role.id}
              >
                <div className="inline-spread">
                  <h2>{role.label}</h2>
                  <label className="check-label role-enable">
                    <input
                      type="checkbox"
                      aria-label={`启用${role.label}模型`}
                      checked={config.enabled}
                      onChange={(event) =>
                        updateRole({ enabled: event.target.checked })
                      }
                    />
                    {config.enabled ? "已启用" : "未启用"}
                  </label>
                </div>
                <p className="muted small role-description">
                  {role.description}
                </p>
                <label>
                  提供方
                  <select
                    aria-label={`${role.label}模型提供方`}
                    aria-describedby={statusId}
                    value={config.provider}
                    onChange={(event) => {
                      setCustomRoles((current) => ({
                        ...current,
                        [role.id]: false,
                      }));
                      updateRole({
                        provider: event.target.value as typeof config.provider,
                      });
                    }}
                  >
                    <option value="codex_cli">Codex CLI</option>
                    <option value="trae_cli">TRAE CLI</option>
                    <option value="claude_code_cli">Claude Code CLI</option>
                  </select>
                </label>
                <p
                  id={statusId}
                  className={`cli-state ${availability?.available === false ? "cli-unavailable" : ""}`}
                >
                  {availability?.available === true
                    ? `已检测到 ${providerLabel}。登录状态由本机 CLI 管理。`
                    : availability?.available === false
                      ? `未检测到 ${providerLabel}，当前不可用。请先在本机安装并登录。`
                      : `尚未取得 ${providerLabel} 的安装检测结果。`}
                </p>
                <div className="form-grid">
                  <div>
                    {config.provider !== "claude_code_cli" && (
                      <label>
                        模型
                        <select
                          aria-label={`${role.label}模型选择`}
                          value={choice}
                          onChange={(event) => {
                            const nextChoice = event.target.value;
                            setCustomRoles((current) => ({
                              ...current,
                              [role.id]: nextChoice === customModelChoice,
                            }));
                            updateRole({
                              model: modelFromChoice(nextChoice, config.model),
                            });
                          }}
                        >
                          <option value={defaultModelChoice}>
                            CLI 默认模型
                          </option>
                          {roleCatalog?.models.map((entry) => (
                            <option
                              key={entry.id}
                              value={catalogModelChoice(entry.id)}
                            >
                              {entry.display_name || entry.id} · {entry.id}
                              {entry.is_default ? "（列表默认）" : ""}
                              {entry.hidden ? "（CLI 隐藏模型）" : ""}
                            </option>
                          ))}
                          <option value={customModelChoice}>自定义模型</option>
                        </select>
                      </label>
                    )}
                    {(config.provider === "claude_code_cli" ||
                      choice === customModelChoice) && (
                      <label>
                        模型名称
                        <input
                          aria-label={`${role.label}模型名称`}
                          value={config.model}
                          maxLength={200}
                          autoComplete="off"
                          placeholder="留空使用 CLI 默认模型"
                          onChange={(event) =>
                            updateRole({ model: event.target.value })
                          }
                        />
                      </label>
                    )}
                    {config.provider === "claude_code_cli" ? (
                      <p className="model-choice-hint">
                        填写 Claude Code CLI 支持的模型 ID；留空使用其默认模型。
                      </p>
                    ) : choice === customModelChoice ? (
                      <p className="model-choice-hint">
                        可填写任意本机 CLI 支持的模型
                        ID；目录外的当前配置会保留。
                      </p>
                    ) : selectedEntry?.description ? (
                      <p className="model-choice-hint">
                        {selectedEntry.description}
                      </p>
                    ) : null}
                  </div>
                  <label>
                    超时（秒）
                    <input
                      aria-label={`${role.label}模型超时秒数`}
                      type="number"
                      min={30}
                      max={1800}
                      step={1}
                      required
                      value={config.timeout_seconds}
                      onChange={(event) =>
                        updateRole({
                          timeout_seconds: Number(event.target.value),
                        })
                      }
                    />
                  </label>
                </div>
              </section>
            );
          })}
        </div>
        <section className="panel form-panel script-discussion-settings">
          <div className="inline-spread">
            <div>
              <h2>文案讨论</h2>
              <p className="muted small">
                编剧和文案审查会按轮数交替工作。审查通过后进入文案人工审核；达到轮数上限仍需修改时，编剧最后改稿一次，再交人工审核。
              </p>
            </div>
          </div>
          <label>
            最大审查轮数
            <input
              aria-label="文案讨论最大审查轮数"
              type="number"
              min={1}
              max={5}
              step={1}
              value={discussionMaxRounds(values)}
              onChange={(event) =>
                onChange(
                  "script_discussion_max_rounds",
                  clampDiscussionRounds(Number(event.target.value)),
                )
              }
            />
          </label>
          <p className="muted small">
            轮数不会自动启用任何 CLI
            模型，也不会对已有任务发起请求；每个角色仍按上面的独立模型配置执行。
          </p>
        </section>
        <div className="settings-section-heading">
          <h2>声音与服务</h2>
          <p className="muted small">配置真实配音、素材检索与音频时间对齐。</p>
        </div>
        <div className="settings-grid">
          {sections.map((section) => (
            <section className="panel form-panel" key={section.title}>
              <h2>{section.title}</h2>
              <p className="muted small">{section.description}</p>
              {section.title === "你的声音" && (
                <label>
                  配音服务
                  <select
                    aria-label="配音服务"
                    value={String(values.voice_provider ?? "none")}
                    onChange={(event) => {
                      const patch = voiceProviderPatch(
                        event.target.value as NonNullable<
                          SettingsPatch["voice_provider"]
                        >,
                      );
                      for (const [key, value] of Object.entries(patch))
                        onChange(key, value);
                    }}
                  >
                    <option value="none">暂未接入</option>
                    <option value="byte_http">字节 HTTP 接口</option>
                    <option value="byte_ws">字节 WebSocket 双向流式</option>
                  </select>
                </label>
              )}
              {section.title === "检索与时间对齐" && (
                <>
                <p className="muted small">
                  启用素材角色并选择 Codex CLI 后，可调用已安装的检索技能查资料和采集真实画面。
                  平台仍可能需要登录、验证码或服务 Key。
                </p>
                <div className="research-skill-list">
                  {(values.research_skills ?? []).map((skill) => (
                    <p className="muted small" key={skill.name}>
                      <strong>{skill.name}</strong>：{skill.installed ? "已安装" : "未安装"} · {skill.detail}
                    </p>
                  ))}
                </div>
                <label>
                  检索服务
                  <select
                    value={String(values.search_provider ?? "none")}
                    onChange={(event) =>
                      onChange("search_provider", event.target.value)
                    }
                  >
                    <option value="none">使用手动来源</option>
                    <option value="opencli_google">OpenCLI Google（本机浏览器）</option>
                    <option value="tavily">Tavily</option>
                    <option value="google_cse">Google CSE</option>
                  </select>
                </label>
                </>
              )}
              {section.fields
                .filter((field) =>
                  showVoiceField(field.key, values.voice_provider),
                )
                .map((field) => (
                  <label key={field.key}>
                    {field.label}
                    {field.secret && (
                      <span className="field-hint">
                        {saved[field.configured ?? ""]
                          ? " ● 已配置"
                          : " ○ 未配置"}
                      </span>
                    )}
                    <input
                      aria-label={field.label}
                      type={field.secret ? "password" : (field.type ?? "text")}
                      min={field.key === "research_max_visuals" ? 0 : field.type === "number" ? 1 : undefined}
                      max={field.key === "research_results_per_platform" ? 5 : field.key === "research_max_searches" ? 32 : field.key === "research_max_sources" ? 30 : field.key === "research_max_visuals" ? 20 : undefined}
                      maxLength={field.key === "voice_model" ? 200 : undefined}
                      list={
                        field.key === "voice_model"
                          ? "voice-model-suggestions"
                          : undefined
                      }
                      required={field.key === "voice_model"}
                      value={String(
                        values[field.key] ??
                          (field.key === "voice_model" ? defaultVoiceModel : ""),
                      )}
                      autoComplete={field.secret ? "new-password" : "off"}
                      placeholder={
                        field.secret
                          ? saved[field.configured ?? ""]
                            ? "•••••••• · 留空保留现有密钥"
                            : "输入密钥（保存后不再显示）"
                          : field.placeholder
                      }
                      onChange={(event) =>
                        onChange(
                          field.key,
                          field.type === "number"
                            ? Number(event.target.value)
                            : event.target.value,
                        )
                      }
                    />
                    {field.key === "voice_model" && (
                      <datalist id="voice-model-suggestions">
                        {voiceModelSuggestions.map((suggestion) => (
                          <option
                            key={suggestion.value}
                            value={suggestion.value}
                            label={suggestion.label}
                          />
                        ))}
                      </datalist>
                    )}
                  </label>
                ))}
              {section.title === "你的声音" &&
                values.voice_provider === "byte_ws" && (
                  <>
                    <label>
                      情感风格预设
                      <select
                        aria-label="情感风格预设"
                        value={selectedVoiceStylePreset(values)}
                        onChange={(event) => {
                          const presetId = event.target.value;
                          onChange("voice_style_preset", presetId);
                          const preset = voiceStylePresets.find(
                            (item) => item.id === presetId,
                          );
                          if (preset) onChange("voice_style", preset.style);
                        }}
                      >
                        <option value={customVoiceStylePreset}>自定义</option>
                        {voiceStylePresets.map((preset) => (
                          <option key={preset.id} value={preset.id}>
                            {preset.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      情感与讲述风格
                      <textarea
                        aria-label="情感与讲述风格"
                        maxLength={2000}
                        value={voiceStyleValue(values)}
                        placeholder={defaultVoiceStyle}
                        onChange={(event) => {
                          onChange("voice_style_preset", customVoiceStylePreset);
                          onChange("voice_style", event.target.value);
                        }}
                      />
                    </label>
                    <label>
                      语速（倍速）
                      <input
                        aria-label="语速（倍速）"
                        type="number"
                        min={0.5}
                        max={2}
                        step={0.01}
                        list="voice-speed-suggestions"
                        value={voiceSpeedMultiplierValue(values)}
                        onChange={(event) =>
                          onChange("voice_speed_multiplier", event.target.value)
                        }
                      />
                      <datalist id="voice-speed-suggestions">
                        {voiceSpeedSuggestions.map((value) => (
                          <option key={value} value={value} />
                        ))}
                      </datalist>
                    </label>
                    <p className="muted small">
                      语速范围 0.5～2.0 倍。情感风格需要
                      seed-tts-2.0-expressive；standard 不支持情感指导。
                    </p>
                  </>
                )}
              {section.title === "你的声音" && (
                <p className="muted small">
                  新版声音复刻默认资源为
                  seed-icl-2.0，请按账号实际开通的资源填写。
                  {values.voice_provider === "byte_ws" &&
                    "语音合成模型可从 expressive/standard 建议中选择，也可自由填写账号支持的模型 ID；该模型与配音角色的 CLI 指导模型独立。"}
                </p>
              )}
              {section.title === "检索与时间对齐" && (
                <>
                  {values.search_provider === "opencli_google" && (
                    <p className="muted small">
                      通过本机 OpenCLI 的 Google 公开搜索检索各平台被索引的页面，无需搜索 API Key。
                      需要 OpenCLI 浏览器扩展连接；页面登录或验证码限制会记录为未完成项。
                    </p>
                  )}
                  {values.search_provider === "google_cse" && (
                    <p className="muted small">
                      Google CSE 使用 Custom Search JSON API。Google
                      官方已提示该产品不再接受新客户，既有客户需在 2027-01-01
                      前迁移；这里保留给已有 CSE 的账号使用。
                    </p>
                  )}
                  <div className="research-tool-list">
                    <p className="muted small">
                      素材 Agent 会按勾选平台尽力研究；下面的工具状态只说明本机已发现的检索入口。
                      搜索调用上限是指令预算，来源与画面数量由接收端校验。
                    </p>
                    {(values.research_tools ?? []).map((tool) => {
                      const selected = (
                        (values.research_platforms as string[] | undefined) ??
                        []
                      ).includes(tool.id);
                      return (
                        <label className="check-label research-tool" key={tool.id}>
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={(event) => {
                              const current = Array.isArray(
                                values.research_platforms,
                              )
                                ? (values.research_platforms as string[])
                                : [];
                              onChange(
                                "research_platforms",
                                event.target.checked
                                  ? [...current, tool.id]
                                  : current.filter((item) => item !== tool.id),
                              );
                            }}
                          />
                          <span>
                            {tool.label}
                            <small>{tool.detail}</small>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={Boolean(values.capture_enabled)}
                      onChange={(event) =>
                        onChange("capture_enabled", event.target.checked)
                      }
                    />
                    启用网页截图
                  </label>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={Boolean(values.research_download_images)}
                      onChange={(event) =>
                        onChange("research_download_images", event.target.checked)
                      }
                    />
                    下载来源页面与搜索结果中的真实图片
                  </label>
                </>
              )}
            </section>
          ))}
        </div>
        <div className="save-bar">
          <span className="muted small">
            密钥只写入后端，不写入浏览器持久存储。
          </span>
          <button className="button primary" disabled={busy}>
            {busy ? "正在保存…" : "保存配置"}
          </button>
        </div>
      </fieldset>
    </form>
  );
}

export function SettingsPage() {
  const [saved, setSaved] = useState<Settings | null>(null);
  const [values, setValues] = useState<Settings>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [modelCatalog, setModelCatalog] = useState<ModelCatalog>();
  const [traeModelCatalog, setTraeModelCatalog] = useState<ModelCatalog>();
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [traeCatalogLoading, setTraeCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState("");
  const [traeCatalogError, setTraeCatalogError] = useState("");
  const catalogRequest = useRef(0);
  const traeCatalogRequest = useRef(0);
  const loadModels = useCallback(async (refresh = false) => {
    const requestId = ++catalogRequest.current;
    setCatalogLoading(true);
    setCatalogError("");
    try {
      const next = await api.models("codex_cli", refresh);
      if (requestId !== catalogRequest.current) return;
      if (next.status === "ready") {
        setModelCatalog(next);
      } else {
        setModelCatalog((current) =>
          current?.status === "ready" ? current : next,
        );
        setCatalogError(next.message || "Codex CLI 模型目录暂不可用。");
      }
    } catch (cause) {
      if (requestId === catalogRequest.current)
        setCatalogError(explainError(cause));
    } finally {
      if (requestId === catalogRequest.current) setCatalogLoading(false);
    }
  }, []);
  const loadTraeModels = useCallback(async (refresh = false) => {
    const requestId = ++traeCatalogRequest.current;
    setTraeCatalogLoading(true);
    setTraeCatalogError("");
    try {
      const next = await api.models("trae_cli", refresh);
      if (requestId !== traeCatalogRequest.current) return;
      if (next.status === "ready") {
        setTraeModelCatalog(next);
      } else {
        setTraeModelCatalog((current) =>
          current?.status === "ready" ? current : next,
        );
        setTraeCatalogError(next.message || "TRAE CLI 模型目录暂不可用。");
      }
    } catch (cause) {
      if (requestId === traeCatalogRequest.current)
        setTraeCatalogError(explainError(cause));
    } finally {
      if (requestId === traeCatalogRequest.current)
        setTraeCatalogLoading(false);
    }
  }, []);
  useEffect(() => {
    void loadModels();
    void loadTraeModels();
    return () => {
      catalogRequest.current += 1;
      traeCatalogRequest.current += 1;
    };
  }, [loadModels, loadTraeModels]);
  useEffect(() => {
    let active = true;
    void api
      .settings()
      .then((settings) => {
        if (active) {
          setSaved(settings);
          setValues({ ...settings, role_models: readRoleModels(settings) });
        }
      })
      .catch((cause: unknown) => {
        if (active) setError(explainError(cause));
      });
    return () => {
      active = false;
    };
  }, []);
  const update = (key: string, value: unknown) => {
    if (busy) return;
    setValues((current) => ({ ...current, [key]: value }));
    setSuccess("");
  };
  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setSuccess("");
    const payload = createSettingsPayload(values, saved ?? {});
    try {
      const next = await api.saveSettings(payload);
      setSaved(next);
      setValues({ ...next, role_models: readRoleModels(next) });
      setSuccess("配置已保存。密钥输入框已清空，服务只返回是否已配置。");
    } catch (cause) {
      setError(explainError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeading eyebrow="MAKE IT YOURS" title="系统设置">
        为素材、编剧、文案审查、配音、导演、剪辑和审核分别选择本机模型，配置你的音色与素材服务。
      </PageHeading>
      {error && <Notice tone="error">{error}</Notice>}
      {success && <Notice tone="success">{success}</Notice>}
      {!saved ? (
        <div className="panel loading">正在读取配置…</div>
      ) : (
        <SettingsForm
          saved={saved}
          values={values}
          busy={busy}
          modelCatalog={modelCatalog}
          traeModelCatalog={traeModelCatalog}
          catalogLoading={catalogLoading}
          traeCatalogLoading={traeCatalogLoading}
          catalogError={catalogError}
          traeCatalogError={traeCatalogError}
          onRefreshModels={() => {
            void loadModels(true);
          }}
          onRefreshTraeModels={() => {
            void loadTraeModels(true);
          }}
          onChange={update}
          onSubmit={(event) => {
            void save(event);
          }}
        />
      )}
    </>
  );
}
