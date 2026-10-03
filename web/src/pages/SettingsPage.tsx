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
          "max_llm_calls" | "max_voice_chars" | "render_timeout_seconds"
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
          | "search_api_key"
          | "aligner_url"
          | "aligner_api_key"
        >;
        type?: "url";
      }
  );
const sections: { title: string; description: string; fields: Field[] }[] = [
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
        label: "Tavily 检索密钥",
        secret: true,
        configured: "search_configured",
      },
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
): Pick<SettingsPatch, "voice_provider" | "voice_endpoint"> {
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
        (field.key === "voice_model" ? "seed-tts-2.0-standard" : undefined);
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
  if (values.search_provider === "none" || values.search_provider === "tavily")
    payload.search_provider = values.search_provider;
  if (typeof values.capture_enabled === "boolean")
    payload.capture_enabled = values.capture_enabled;
  const roles = buildRoleModelsPatch(
    readRoleModels(values),
    readRoleModels(saved),
  );
  if (Object.keys(roles).length) payload.role_models = roles;
  return payload;
}

interface SettingsFormProps {
  saved: Settings;
  values: Settings;
  busy: boolean;
  modelCatalog?: ModelCatalog;
  catalogLoading?: boolean;
  catalogError?: string;
  onRefreshModels?: () => void;
  onChange: (key: string, value: unknown) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function SettingsForm({
  saved,
  values,
  busy,
  modelCatalog,
  catalogLoading = false,
  catalogError = "",
  onRefreshModels,
  onChange,
  onSubmit,
}: SettingsFormProps) {
  const roles = readRoleModels(values);
  const [customRoles, setCustomRoles] = useState<
    Partial<Record<RoleId, boolean>>
  >({});
  const codexCatalog =
    modelCatalog?.provider === "codex_cli" ? modelCatalog : undefined;
  return (
    <form onSubmit={onSubmit} aria-busy={busy}>
      <fieldset className="editor-fieldset" disabled={busy}>
        <div className="settings-section-heading">
          <h2>五个角色的模型</h2>
          <p className="muted small">
            各角色独立选择本机 CLI 和模型。留空模型名称时使用该 CLI 的默认模型。
            检测只确认是否安装；运行前请在本机完成相应 CLI 登录。
            仅影响后续实际调用；已有文案、分镜和产物不会自动重做。
          </p>
        </div>
        <div
          className="model-catalog-status"
          aria-live="polite"
          aria-busy={catalogLoading}
        >
          <div className="inline-spread">
            <strong>Codex CLI 本机模型列表</strong>
            {onRefreshModels && (
              <button
                type="button"
                className="button secondary small"
                aria-label="重读 Codex 模型列表"
                disabled={catalogLoading || busy}
                onClick={onRefreshModels}
              >
                {catalogLoading ? "正在读取…" : "重读模型列表"}
              </button>
            )}
          </div>
          <p className="muted small">
            {catalogLoading
              ? "正在读取模型列表；仍可编辑角色配置。"
              : codexCatalog?.status === "ready"
                ? `已读取 ${codexCatalog.models.length} 个模型，含隐藏项。`
                : "目录尚不可用，可选择 CLI 默认模型或填写自定义模型 ID。"}
          </p>
          <p className="muted small">
            从本机 Codex
            模型缓存读取，重读列表只读取该缓存。可选列表不代表当前账号权限，实际支持以
            CLI 调用为准。
          </p>
          {codexCatalog?.fetched_at && (
            <p className="muted small">
              缓存生成时间（本地）：
              <time dateTime={codexCatalog.fetched_at}>
                {formatModelCacheTime(codexCatalog.fetched_at)}
              </time>
            </p>
          )}
          {catalogError ? (
            <p className="catalog-error">
              {catalogError}
              {codexCatalog?.status === "ready" && " 当前保留上次读取的列表。"}
              角色配置保持不变，可继续使用默认或自定义模型。
            </p>
          ) : codexCatalog?.status !== "ready" && codexCatalog?.message ? (
            <p className="muted small">{codexCatalog.message}</p>
          ) : null}
        </div>
        <div className="settings-grid role-model-grid">
          {modelRoles.map((role) => {
            const config = roles[role.id];
            const availability = saved.cli_availability?.[config.provider];
            const providerLabel =
              config.provider === "codex_cli" ? "Codex CLI" : "Claude Code CLI";
            const updateRole = (changes: Partial<typeof config>) => {
              onChange("role_models", {
                ...roles,
                [role.id]: { ...config, ...changes },
              });
            };
            const statusId = `role-cli-status-${role.id}`;
            const choice = selectedModelChoice(
              config.model,
              codexCatalog,
              customRoles[role.id],
            );
            const selectedEntry = codexCatalog?.models.find(
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
                    onChange={(event) =>
                      updateRole({
                        provider: event.target.value as typeof config.provider,
                      })
                    }
                  >
                    <option value="codex_cli">Codex CLI</option>
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
                    {config.provider === "codex_cli" && (
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
                          {codexCatalog?.models.map((entry) => (
                            <option
                              key={entry.id}
                              value={catalogModelChoice(entry.id)}
                            >
                              {entry.display_name || entry.id} · {entry.id}
                              {entry.is_default ? "（目录默认）" : ""}
                              {entry.hidden ? "（目录隐藏项）" : ""}
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
                <label>
                  检索服务
                  <select
                    value={String(values.search_provider ?? "none")}
                    onChange={(event) =>
                      onChange("search_provider", event.target.value)
                    }
                  >
                    <option value="none">使用手动来源</option>
                    <option value="tavily">Tavily</option>
                  </select>
                </label>
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
                      min={field.type === "number" ? 1 : undefined}
                      maxLength={field.key === "voice_model" ? 200 : undefined}
                      required={field.key === "voice_model"}
                      value={String(
                        values[field.key] ??
                          (field.key === "voice_model"
                            ? "seed-tts-2.0-standard"
                            : ""),
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
                  </label>
                ))}
              {section.title === "你的声音" && (
                <p className="muted small">
                  新版声音复刻默认资源为
                  seed-icl-2.0，请按账号实际开通的资源填写。
                  {values.voice_provider === "byte_ws" &&
                    "语音合成模型用于字节生成声音，与配音角色的 CLI 指导模型独立。"}
                </p>
              )}
              {section.title === "检索与时间对齐" && (
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
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState("");
  const catalogRequest = useRef(0);
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
  useEffect(() => {
    void loadModels();
    return () => {
      catalogRequest.current += 1;
    };
  }, [loadModels]);
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
        为编剧、配音、导演、剪辑和审核分别选择本机模型，配置你的音色与素材服务。
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
          catalogLoading={catalogLoading}
          catalogError={catalogError}
          onRefreshModels={() => {
            void loadModels(true);
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
