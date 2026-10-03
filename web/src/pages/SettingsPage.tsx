import { useEffect, useState, type FormEvent } from "react";
import { api, explainError } from "../api/client";
import {
  buildRoleModelsPatch,
  modelRoles,
  readRoleModels,
} from "../api/roleSettings";
import type { Settings, SettingsPatch } from "../api/types";
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
      { key: "voice_resource_id", label: "资源 ID" },
      { key: "voice_id", label: "音色 ID" },
      {
        key: "voice_access_token",
        label: "访问令牌",
        secret: true,
        configured: "voice_configured",
      },
      {
        key: "voice_api_key",
        label: "新鉴权 API Key（按你的接口填写）",
        secret: true,
        configured: "voice_configured",
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

export function createSettingsPayload(
  values: Settings,
  saved: Settings,
): SettingsPatch {
  const payload: SettingsPatch = {};
  for (const section of sections) {
    for (const field of section.fields) {
      const value = values[field.key];
      if (field.secret && !value) continue; // Blank preserves the configured secret.
      if (field.type === "number") {
        if (typeof value === "number") payload[field.key] = value;
      } else if (typeof value === "string") {
        payload[field.key] = value;
      }
    }
  }
  if (values.voice_provider === "none" || values.voice_provider === "byte_http")
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
  onChange: (key: string, value: unknown) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function SettingsForm({
  saved,
  values,
  busy,
  onChange,
  onSubmit,
}: SettingsFormProps) {
  const roles = readRoleModels(values);
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
                    value={String(values.voice_provider ?? "none")}
                    onChange={(event) =>
                      onChange("voice_provider", event.target.value)
                    }
                  >
                    <option value="none">暂未接入</option>
                    <option value="byte_http">字节 HTTP 接口</option>
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
              {section.fields.map((field) => (
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
                    type={field.secret ? "password" : (field.type ?? "text")}
                    min={field.type === "number" ? 1 : undefined}
                    value={String(values[field.key] ?? "")}
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
          onChange={update}
          onSubmit={(event) => {
            void save(event);
          }}
        />
      )}
    </>
  );
}
