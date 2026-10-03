import { useEffect, useState, type FormEvent } from "react";
import { api, explainError } from "../api/client";
import type { Settings } from "../api/types";
import { Notice, PageHeading } from "../components/ui";

interface Field {
  key: string;
  label: string;
  placeholder?: string;
  secret?: boolean;
  type?: "number" | "url";
  configured?: string;
}
const sections: { title: string; description: string; fields: Field[] }[] = [
  {
    title: "编剧与导演模型",
    description: "模型用于生成文案和结构化分镜。",
    fields: [
      {
        key: "llm_base_url",
        label: "API 地址",
        placeholder: "https://…/v1",
        type: "url",
      },
      { key: "llm_model", label: "模型名称" },
      {
        key: "llm_api_key",
        label: "API 密钥",
        secret: true,
        configured: "llm_configured",
      },
    ],
  },
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
          setValues(settings);
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
    setValues((current) => ({ ...current, [key]: value }));
    setSuccess("");
  };
  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setSuccess("");
    const payload: Settings = {};
    for (const section of sections)
      for (const field of section.fields) {
        const value = values[field.key];
        if (field.secret && !value) continue; // Blank means preserve the configured secret.
        if (value !== undefined) payload[field.key] = value;
      }
    for (const key of ["voice_provider", "search_provider", "capture_enabled"])
      if (values[key] !== undefined) payload[key] = values[key];
    try {
      const next = await api.saveSettings(payload);
      setSaved(next);
      setValues(next);
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
        配置模型、音色与检索服务，让工作流使用你的能力。
      </PageHeading>
      {error && <Notice tone="error">{error}</Notice>}
      {success && <Notice tone="success">{success}</Notice>}
      {!saved ? (
        <div className="panel loading">正在读取配置…</div>
      ) : (
        <form
          onSubmit={(event) => {
            void save(event);
          }}
        >
          <fieldset className="editor-fieldset" disabled={busy}>
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
                          update("voice_provider", event.target.value)
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
                          update("search_provider", event.target.value)
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
                        type={
                          field.secret ? "password" : (field.type ?? "text")
                        }
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
                          update(
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
                          update("capture_enabled", event.target.checked)
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
      )}
    </>
  );
}
