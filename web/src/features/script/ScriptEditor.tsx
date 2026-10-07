import { useEffect, useState } from "react";
import { api, explainError } from "../../api/client";
import type { Job, Script, ScriptSegment } from "../../api/types";
import { Notice } from "../../components/ui";

function initialScript(job: Job): Script {
  return (
    job.script ?? {
      title:
        job.brief.topic || (job.brief.creative_direction || job.brief.script_text).slice(0, 40) || "我的视频",
      title_hook: "",
      opening_visual: "",
      final_answer: "",
      origin: "user",
      revision: job.revision,
      segments: [
        {
          segment_id: crypto.randomUUID(),
          narration: job.brief.script_text,
          screen_text: "",
          source_refs: job.brief.source_urls,
          asset_ids: [],
        },
      ],
    }
  );
}

export function ScriptEditor({
  job,
  onUpdate,
  locked,
  onDirty,
}: {
  job: Job;
  onUpdate: (job: Job) => void;
  locked: boolean;
  onDirty: (dirty: boolean) => void;
}) {
  const [draft, setDraft] = useState<Script>(() => initialScript(job));
  const [baseRevision, setBaseRevision] = useState(job.revision);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);
  useEffect(() => {
    if (!dirty) {
      setDraft(initialScript(job));
      setBaseRevision(job.revision);
    }
  }, [job, dirty]);
  const update = (index: number, change: Partial<ScriptSegment>) => {
    setDirty(true);
    setDraft((current) => ({
      ...current,
      segments: current.segments.map((segment, position) =>
        position === index ? { ...segment, ...change } : segment,
      ),
    }));
  };
  const updateScript = (change: Partial<Script>) => {
    setDirty(true);
    setDraft((current) => ({ ...current, ...change }));
  };
  const save = async () => {
    if (busy || locked) return;
    setBusy(true);
    setError("");
    try {
      const next = await api.saveDraft(job.job_id, baseRevision, {
        script: { ...draft, origin: "user" },
      });
      onUpdate(next);
      setDirty(false);
    } catch (cause) {
      setError(explainError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <fieldset
      className="feature-section editor-fieldset"
      disabled={locked || busy}
    >
      <div className="section-heading">
        <div>
          <h2>口播文案</h2>
          <p>每段声音对应画面要点、来源与真实素材。</p>
        </div>
        <button
          className="button primary"
          disabled={busy || locked || !dirty}
          onClick={() => {
            void save();
          }}
        >
          {busy ? "正在保存…" : "保存文案"}
        </button>
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {dirty && baseRevision !== job.revision && (
        <Notice tone="error">
          你编辑期间任务已更新。当前草稿仍保留；保存前请核对新版本，避免覆盖。
        </Notice>
      )}
      {dirty && (
        <details className="panel draft-comparison">
          <summary>与已保存文案对比</summary>
          <div className="form-panel form-grid">
            <div>
              <h3>当前保存 · 第 {job.revision} 版</h3>
              <p>
                {job.script?.segments
                  .map((segment) => segment.narration)
                  .join("\n\n") || job.brief.script_text || "尚无已保存文案"}
              </p>
            </div>
            <div>
              <h3>我的编辑草稿</h3>
              <p>
                {draft.segments
                  .map((segment) => segment.narration)
                  .join("\n\n")}
              </p>
            </div>
          </div>
          <button
            className="text-button"
            disabled={locked}
            onClick={() => {
              setDirty(false);
              setError("");
            }}
          >
            放弃本地编辑，使用已保存版本
          </button>
        </details>
      )}
      <div className="panel form-panel">
        <label>
          视频标题
          <input
            value={draft.title}
            maxLength={300}
            disabled={locked}
            onChange={(event) => updateScript({ title: event.target.value })}
          />
        </label>
        <div className="form-grid">
          <label>
            前3秒画面字
            <input
              value={draft.title_hook}
              maxLength={15}
              disabled={locked}
              onChange={(event) =>
                updateScript({ title_hook: event.target.value })
              }
              placeholder="15字以内"
            />
            <small className="muted">
              创作信息，用来审开头屏幕字，不会当成口播。
            </small>
          </label>
          <label>
            开头画面建议
            <input
              value={draft.opening_visual}
              maxLength={300}
              disabled={locked}
              onChange={(event) =>
                updateScript({ opening_visual: event.target.value })
              }
              placeholder="一句话说明前3秒该看到什么"
            />
          </label>
        </div>
        <label>
          一句主答案
          <input
            value={draft.final_answer}
            maxLength={300}
            disabled={locked}
            onChange={(event) =>
              updateScript({ final_answer: event.target.value })
            }
            placeholder="给观众带走的一句话，不替代段落口播"
          />
        </label>
      </div>
      {draft.segments.map((segment, index) => (
        <article className="panel segment-card" key={segment.segment_id}>
          <div className="inline-spread">
            <h3>
              <span className="number-label">
                {String(index + 1).padStart(2, "0")}
              </span>{" "}
              口播段落
            </h3>
            <button
              className="text-button danger-text"
              disabled={locked || draft.segments.length === 1}
              onClick={() => {
                setDirty(true);
                setDraft((current) => ({
                  ...current,
                  segments: current.segments.filter(
                    (item) => item.segment_id !== segment.segment_id,
                  ),
                }));
              }}
            >
              移除段落
            </button>
          </div>
          <label>
            口播内容
            <textarea
              rows={4}
              value={segment.narration}
              disabled={locked}
              onChange={(event) =>
                update(index, { narration: event.target.value })
              }
            />
          </label>
          <label>
            画面文字
            <input
              value={segment.screen_text}
              maxLength={240}
              disabled={locked}
              onChange={(event) =>
                update(index, { screen_text: event.target.value })
              }
              placeholder="一句关键表达，不用重复全部口播"
            />
          </label>
          <div className="form-grid">
            <label>
              事实来源
              <textarea
                rows={3}
                value={segment.source_refs.join("\n")}
                disabled={locked}
                onChange={(event) =>
                  update(index, {
                    source_refs: event.target.value
                      .split("\n")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  })
                }
                placeholder="每行一个来源地址"
              />
            </label>
            <div>
              <span className="label">对应素材</span>
              <div className="asset-checks">
                {job.assets.filter((asset) => asset.role !== "audio").length ? (
                  job.assets
                    .filter((asset) => asset.role !== "audio")
                    .map((asset) => (
                      <label key={asset.asset_id} className="check-label">
                        <input
                          type="checkbox"
                          checked={segment.asset_ids.includes(asset.asset_id)}
                          disabled={locked}
                          onChange={(event) =>
                            update(index, {
                              asset_ids: event.target.checked
                                ? [...segment.asset_ids, asset.asset_id]
                                : segment.asset_ids.filter(
                                    (id) => id !== asset.asset_id,
                                  ),
                            })
                          }
                        />
                        {asset.name}
                      </label>
                    ))
                ) : (
                  <small className="muted">
                    在「素材」上传真实图片或截图后选择。
                  </small>
                )}
              </div>
            </div>
          </div>
        </article>
      ))}
      <button
        className="button secondary"
        disabled={locked}
        onClick={() => {
          setDirty(true);
          setDraft((current) => ({
            ...current,
            segments: [
              ...current.segments,
              {
                segment_id: crypto.randomUUID(),
                narration: "",
                screen_text: "",
                source_refs: [],
                asset_ids: [],
              },
            ],
          }));
        }}
      >
        ＋ 添加口播段落
      </button>
      <p className="muted small">
        保存新文案后，配音、分镜与旧审核结论会按依赖重新生成。
      </p>
    </fieldset>
  );
}
