import { useState, type FormEvent } from "react";
import { api, explainError } from "../api/client";
import type { Brief } from "../api/types";
import { navigate } from "../app/router";
import { Notice, PageHeading } from "../components/ui";

const initialBrief: Brief = {
  topic: "",
  creative_direction: "",
  script_text: "",
  audience: "没有技术背景的普通大众",
  platform: "抖音",
  usage: "unspecified",
  target_seconds: 60,
  width: 1080,
  height: 1920,
  fps: 30,
  source_urls: [],
};

export function CreateJobPage() {
  const [brief, setBrief] = useState<Brief>(initialBrief);
  const [sources, setSources] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const change = <K extends keyof Brief>(key: K, value: Brief[K]) =>
    setBrief((current) => ({ ...current, [key]: value }));
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (!brief.topic.trim() && !brief.creative_direction.trim()) {
      setError("请填写主题或本期创作方向。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const job = await api.createJob({
        ...brief,
        platform: "抖音",
        width: 1080,
        height: 1920,
        fps: 30,
        source_urls: sources
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
      });
      navigate(`/jobs/${job.job_id}`);
    } catch (cause) {
      setError(explainError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeading eyebrow="START WITH AN IDEA" title="新建视频">
        先保存制作需求，进入工作台后上传素材、配音并开始制作。
      </PageHeading>
      <form
        onSubmit={(event) => {
          void submit(event);
        }}
      >
        <fieldset className="create-layout editor-fieldset" disabled={busy}>
          <div className="panel form-panel">
            <h2>你想讲什么？</h2>
            <label>
              视频主题
              <input
                value={brief.topic}
                onChange={(event) => change("topic", event.target.value)}
                placeholder="例如：用 60 秒讲清 AI 如何帮你完成工作"
                maxLength={300}
              />
            </label>
            <label>
              本期创作方向
              <textarea
                rows={10}
                value={brief.creative_direction}
                onChange={(event) => change("creative_direction", event.target.value)}
                placeholder="写你想讲的问题、角度、重点或希望观众看完明白什么；不需要写成口播稿。"
              />
            </label>
            <label>
              参考来源
              <textarea
                rows={3}
                value={sources}
                onChange={(event) => setSources(event.target.value)}
                placeholder="每行一个网页地址；真实截图、图片和视频可在下一步上传"
              />
            </label>
          </div>
          <aside className="panel form-panel">
            <h2>制作要求</h2>
            <Notice>抖音竖屏 · 1080 × 1920 · 30 fps</Notice>
            <label>
              目标观众
              <input
                value={brief.audience}
                onChange={(event) => change("audience", event.target.value)}
                required
              />
            </label>
            <label>
              目标时长（秒）
              <input
                type="number"
                min="5"
                max="1800"
                value={brief.target_seconds}
                onChange={(event) =>
                  change("target_seconds", Number(event.target.value))
                }
                required
              />
            </label>
            <label>
              素材与组件用途
              <select
                value={brief.usage}
                onChange={(event) =>
                  change("usage", event.target.value as Brief["usage"])
                }
              >
                <option value="unspecified">待确认</option>
                <option value="personal">个人用途</option>
                <option value="commercial">商业用途</option>
              </select>
            </label>
            <p className="muted small">
              用途会参与最终审核，商业视频需要相应的素材与组件授权。
            </p>
            {error && <Notice tone="error">{error}</Notice>}
            <button
              className="button primary full-width"
              disabled={busy}
              type="submit"
            >
              {busy ? "正在保存…" : "创建制作任务 →"}
            </button>
            <a href="#/" className="quiet-link">
              返回任务列表
            </a>
          </aside>
        </fieldset>
      </form>
    </>
  );
}
