import { useEffect, useState } from "react";
import { api, explainError } from "../../api/client";
import type {
  Asset,
  ComponentEntry,
  Job,
  RunAction,
  Shot,
  Timeline,
} from "../../api/types";
import { Empty, Notice } from "../../components/ui";
import {
  componentNames,
  defaultProps,
  isCommunityComponent,
  removeShot,
  splitShot,
  validateTimeline,
} from "./timeline";
import { ShotPropsEditor } from "./ShotPropsEditor";

export function StoryboardEditor({
  job,
  onUpdate,
  run,
  locked,
  seek,
  onDirty,
}: {
  job: Job;
  onUpdate: (job: Job) => void;
  run: (action: RunAction) => void;
  locked: boolean;
  seek: (seconds: number) => void;
  onDirty: (dirty: boolean) => void;
}) {
  const [timeline, setTimeline] = useState<Timeline | null>(job.timeline);
  const [baseRevision, setBaseRevision] = useState(job.revision);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [catalog, setCatalog] = useState<ComponentEntry[]>([]);
  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);
  useEffect(() => {
    if (!dirty) {
      setTimeline(job.timeline);
      setBaseRevision(job.revision);
    }
  }, [job, dirty]);
  useEffect(() => {
    void api
      .catalog()
      .then(setCatalog)
      .catch((cause: unknown) => setError(explainError(cause)));
  }, []);
  const update = (index: number, changes: Partial<Shot>) => {
    setDirty(true);
    setTimeline((current) =>
      current
        ? {
            ...current,
            shots: current.shots.map((shot, position) =>
              position === index ? { ...shot, ...changes } : shot,
            ),
          }
        : current,
    );
  };
  const save = async () => {
    if (!timeline || busy || locked) return;
    setError("");
    const errors = validateTimeline(timeline);
    if (errors.length) {
      setError(errors.join(" "));
      return;
    }
    setBusy(true);
    try {
      const next = await api.saveDraft(job.job_id, baseRevision, { timeline });
      onUpdate(next);
      setDirty(false);
    } catch (cause) {
      setError(explainError(cause));
    } finally {
      setBusy(false);
    }
  };
  const transform = (index: number, operation: typeof splitShot) => {
    if (!timeline) return;
    try {
      setTimeline(operation(timeline, index));
      setDirty(true);
      setError("");
    } catch (cause) {
      setError(explainError(cause));
    }
  };
  const images = job.assets.filter((asset) =>
    asset.mime_type.startsWith("image/"),
  );
  const videos = job.assets.filter((asset) => asset.mime_type === "video/mp4");
  const allVisualAssets = [...images, ...videos];
  const catalogWithVideo: ComponentEntry[] = [
    {
      component_id: "video",
      name: "真实视频",
      description: "真实 MP4 素材片段",
      use_case: "产品演示、实拍证据、动态素材",
      library: "VideoAgents",
      kind: "adapter",
      orientation: "vertical",
      production_ready: true,
      min_frames: 1,
      allowed_usages: ["personal", "commercial", "unspecified"],
      license_note: "使用当前任务上传或素材节点采集的视频，发布前需核验授权。",
      preview_url: null,
    },
    ...catalog,
  ];
  const assetChoices = (shot: Shot) => {
    if (shot.component_id === "video") return videos;
    if (["evidence", "image_focus"].includes(shot.component_id)) return images;
    return [];
  };
  const mediaCapable = (componentId: string) =>
    componentId === "video" || ["evidence", "image_focus"].includes(componentId);
  const compatibleAssetSrc = (componentId: string, assetSrc: string | null) => {
    if (!mediaCapable(componentId) || !assetSrc) return null;
    const asset = allVisualAssets.find((item) => item.timeline_src === assetSrc);
    if (!asset) return null;
    if (componentId === "video")
      return asset.mime_type === "video/mp4" ? assetSrc : null;
    return asset.mime_type.startsWith("image/") ? assetSrc : null;
  };
  return (
    <fieldset
      className="feature-section editor-fieldset"
      disabled={locked || busy}
    >
      <div className="section-heading">
        <div>
          <h2>导演分镜</h2>
          <p>按音频节奏选择镜头内容、重点和运动。</p>
        </div>
        <div className="button-row">
          <button
            className="button secondary"
            disabled={locked || !job.script}
            onClick={() => run("storyboard")}
          >
            生成分镜
          </button>
          <button
            className="button primary"
            disabled={locked || busy || !dirty}
            onClick={() => {
              void save();
            }}
          >
            {busy ? "正在保存…" : "保存分镜"}
          </button>
        </div>
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {dirty && baseRevision !== job.revision && (
        <Notice tone="error">
          任务已有新版本，当前分镜草稿仍保留。保存将执行版本校验。
        </Notice>
      )}
      {!timeline ? (
        <Empty title="还没有分镜">
          完成配音与时间对齐后，导演会根据实际声音生成镜头。
        </Empty>
      ) : (
        <>
          <div className="timeline-summary panel">
            <strong>{timeline.shots.length} 个镜头</strong>
            <span>
              {(timeline.duration_in_frames / timeline.fps).toFixed(2)} 秒
            </span>
            <span>
              {timeline.width} × {timeline.height} · {timeline.fps} fps
            </span>
            <small className="muted">边界以帧为准，修改后需重新渲染。</small>
          </div>
          <div className="shot-list">
            {timeline.shots.map((shot, index) => {
              const selectedAsset = allVisualAssets.find(
                (asset) => asset.timeline_src === shot.asset_src,
              );
              const choices = assetChoices(shot);
              return (
                <article className="panel shot-card" key={shot.shot_id}>
                  <div className="shot-overview">
                    <span className="number-label large">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div
                      className="shot-thumbnail"
                      style={{ borderColor: shot.accent_color }}
                    >
                      {selectedAsset ? (
                        <AssetThumbnail asset={selectedAsset} />
                      ) : (
                        <strong style={{ color: shot.accent_color }}>
                          {shot.title}
                        </strong>
                      )}
                    </div>
                    <div>
                      <strong>
                        {(shot.start_frame / timeline.fps).toFixed(2)} –{" "}
                        {(shot.end_frame / timeline.fps).toFixed(2)} 秒
                      </strong>
                      <small className="muted">
                        {componentNames[shot.component_id] ?? shot.component_id}
                      </small>
                      <button
                        className="text-button"
                        onClick={() => seek(shot.start_frame / timeline.fps)}
                      >
                        在视频中定位 ↗
                      </button>
                    </div>
                    <div className="shot-actions">
                      <button
                        className="text-button"
                        disabled={locked}
                        onClick={() => transform(index, splitShot)}
                      >
                        拆分镜头
                      </button>
                      <button
                        className="text-button danger-text"
                        disabled={locked || timeline.shots.length === 1}
                        onClick={() => transform(index, removeShot)}
                      >
                        移除并合并时长
                      </button>
                    </div>
                  </div>
                  <div className="form-grid shot-fields">
                    <label>
                      画面组件
                      <select
                        value={shot.component_id}
                        disabled={locked}
                        onChange={(event) => {
                          const componentId = event.target.value;
                          update(index, {
                            component_id: componentId as Shot["component_id"],
                            props: defaultProps(componentId),
                            asset_src: compatibleAssetSrc(
                              componentId,
                              shot.asset_src,
                            ),
                          });
                        }}
                      >
                        {catalogWithVideo
                          .filter(
                            (entry) =>
                              entry.production_ready &&
                              entry.allowed_usages.includes(job.brief.usage),
                          )
                          .map((entry) => (
                            <option
                              value={entry.component_id}
                              key={entry.component_id}
                            >
                              {entry.name}
                            </option>
                          ))}
                      </select>
                    </label>
                    <div className="form-grid">
                      <label>
                        开始帧
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={shot.start_frame}
                          disabled={locked}
                          onChange={(event) =>
                            update(index, {
                              start_frame: Number(event.target.value),
                            })
                          }
                        />
                      </label>
                      <label>
                        结束帧
                        <input
                          type="number"
                          min="1"
                          step="1"
                          value={shot.end_frame}
                          disabled={locked}
                          onChange={(event) =>
                            update(index, {
                              end_frame: Number(event.target.value),
                            })
                          }
                        />
                      </label>
                    </div>
                    <label>
                      画面标题
                      <input
                        value={shot.title}
                        maxLength={100}
                        disabled={locked}
                        onChange={(event) =>
                          update(index, { title: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      画面文字
                      <textarea
                        rows={2}
                        value={shot.body}
                        maxLength={240}
                        disabled={locked}
                        onChange={(event) =>
                          update(index, { body: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      {shot.component_id === "video" ? "视频素材" : "画面素材"}
                      <select
                        value={shot.asset_src ?? ""}
                        disabled={locked || isCommunityComponent(shot.component_id)}
                        onChange={(event) =>
                          update(index, {
                            asset_src: event.target.value || null,
                          })
                        }
                      >
                        <option value="">
                          {shot.component_id === "video"
                            ? "不使用视频"
                            : ["evidence", "image_focus"].includes(shot.component_id)
                              ? "不使用图片"
                              : "该组件不使用素材"}
                        </option>
                        {choices.map((asset) => (
                          <option
                            key={asset.asset_id}
                            value={asset.timeline_src}
                          >
                            {asset.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      来源说明
                      <input
                        value={shot.source_label}
                        maxLength={160}
                        disabled={locked}
                        onChange={(event) =>
                          update(index, { source_label: event.target.value })
                        }
                      />
                    </label>
                  </div>
                  <div className="shot-detail-fields">
                    <label className="color-label">
                      主题色
                      <input
                        type="color"
                        value={shot.accent_color}
                        disabled={locked}
                        onChange={(event) =>
                          update(index, { accent_color: event.target.value })
                        }
                      />
                    </label>
                    <ShotPropsEditor
                      shot={shot}
                      disabled={locked}
                      update={(props) => update(index, { props })}
                    />
                  </div>
                </article>
              );
            })}
          </div>
        </>
      )}
    </fieldset>
  );
}

function AssetThumbnail({ asset }: { asset: Asset }) {
  if (asset.mime_type.startsWith("video/"))
    return (
      <video
        src={asset.url}
        muted
        preload="metadata"
        aria-label={asset.name}
        style={{ width: "100%", height: "100%", objectFit: "contain" }}
      />
    );
  return <img src={asset.url} alt={asset.name} />;
}
