import type { DirectorShotReviewManifest } from "../../../../contracts/generated/models";

export function DirectorShotReviewGallery({
  manifest, loadedShotIds, reviewedShotIds, failedShotIds, feedback, locked,
  onImageLoad, onImageError, onReviewedChange, onFeedbackChange,
}: {
  manifest: DirectorShotReviewManifest;
  loadedShotIds: ReadonlySet<string>;
  reviewedShotIds: ReadonlySet<string>;
  failedShotIds: ReadonlySet<string>;
  feedback: Record<string, string>;
  locked: boolean;
  onImageLoad: (shotId: string) => void;
  onImageError: (shotId: string) => void;
  onReviewedChange: (shotId: string, reviewed: boolean) => void;
  onFeedbackChange: (shotId: string, note: string) => void;
}) {
  const reviewed = manifest.items.filter((item) => reviewedShotIds.has(item.shot_id)).length;
  return (
    <div className="director-shot-review">
      <div className="inline-spread">
        <h3>逐镜画面审核</h3>
        <strong>已阅 {reviewed} / {manifest.items.length} 个镜头</strong>
      </div>
      <p className="muted small">按镜头顺序核对实际渲染图片、口播和组件选择。所有镜头逐一勾选已阅后，再确认整套方案并开始完整成片。</p>
      <div className="director-shot-review-list">
        {manifest.items.map((item) => {
          const loaded = loadedShotIds.has(item.shot_id);
          const failed = failedShotIds.has(item.shot_id);
          return (
            <article className="director-shot-review-card" key={item.shot_id} id={`shot-review-${item.shot_id}`}>
              <div className="director-shot-image">
                <a href={item.image.url} target="_blank" rel="noreferrer" aria-label={`打开镜头 ${item.index} 原尺寸图片`}>
                  <img src={item.image.url} alt={`镜头 ${item.index}：${item.title}`} loading="lazy"
                    onLoad={(event) => {
                      if (event.currentTarget.naturalWidth > 0 && event.currentTarget.naturalHeight > 0) onImageLoad(item.shot_id);
                      else onImageError(item.shot_id);
                    }} onError={() => onImageError(item.shot_id)} />
                </a>
                {!loaded && !failed && <small className="muted">正在读取实际渲染图片…</small>}
                {failed && <small className="danger-text">图片读取失败，请刷新后重试；此镜头不能标为已阅。</small>}
                <a href={item.image.url} download={item.image.name}>下载原尺寸 PNG ↓</a>
              </div>
              <div className="director-shot-details">
                <div className="inline-spread">
                  <h4>镜头 {String(item.index).padStart(2, "0")} · {item.title}</h4>
                  <span className="number-label">{reviewedShotIds.has(item.shot_id) ? "已阅" : "待阅"}</span>
                </div>
                <small className="muted">{item.shot_id} · {(item.start_frame / manifest.fps).toFixed(2)}–{(item.end_frame / manifest.fps).toFixed(2)} 秒 · 审核帧 {item.review_frame}（{(item.review_frame / manifest.fps).toFixed(2)} 秒）</small>
                <dl>
                  <dt>组件选择</dt><dd>{item.set_id ? `组件套 ${item.set_id}` : `单组件 ${item.component_id}`}</dd>
                  <dt>实际执行组件</dt><dd>{item.component_ids.join(" / ")}</dd>
                  <dt>本镜头口播</dt><dd>{item.narration || "此镜头没有口播"}</dd>
                  <dt>选择原因</dt><dd>{item.component_reason}</dd>
                  <dt>画面如何表演</dt><dd>{item.visual_action}</dd>
                  {item.asset_src && <><dt>素材</dt><dd>{item.asset_src}</dd></>}
                  {item.source_label && <><dt>来源说明</dt><dd>{item.source_label}</dd></>}
                </dl>
                <label>镜头返工意见
                  <textarea rows={2} value={feedback[item.shot_id] ?? ""} disabled={locked}
                    onChange={(event) => onFeedbackChange(item.shot_id, event.target.value)}
                    placeholder="例如：A05应保留原图和独立放大窗" maxLength={1000} />
                </label>
                <label className="check-label"><input type="checkbox" checked={reviewedShotIds.has(item.shot_id)}
                  disabled={locked || !loaded || failed} onChange={(event) => onReviewedChange(item.shot_id, event.target.checked)} />
                  我已审阅此镜头的实际画面、口播和组件选择
                </label>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
