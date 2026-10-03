import { useState, type FormEvent } from "react";
import { api, explainError } from "../../api/client";
import type { Job } from "../../api/types";
import { Empty, formatBytes, Notice } from "../../components/ui";

const roleNames: Record<string, string> = {
  evidence: "事实证据",
  illustration: "概念示意",
  decoration: "装饰画面",
  audio: "音频",
};

export function AssetsPanel({
  job,
  refresh,
  locked,
}: {
  job: Job;
  refresh: () => Promise<unknown>;
  locked: boolean;
}) {
  const [role, setRole] = useState("evidence");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const upload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || locked) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const file = data.get("file");
    if (!(file instanceof File) || !file.size) {
      setError("请先选择图片或截图。");
      return;
    }
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api.upload(job.job_id, data);
      await refresh();
      form.reset();
      setRole("evidence");
      setSuccess("素材已保存，可以在文案与分镜中选择。");
    } catch (cause) {
      setError(explainError(cause));
    } finally {
      setBusy(false);
    }
  };
  const assets = job.assets.filter((asset) => asset.role !== "audio");
  return (
    <fieldset
      className="feature-section editor-fieldset"
      disabled={locked || busy}
    >
      <div className="section-heading">
        <div>
          <h2>真实素材</h2>
          <p>保留出处和用途说明，让证据镜头可核对。</p>
        </div>
        <span className="badge">{assets.length} 个素材</span>
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {success && <Notice tone="success">{success}</Notice>}
      <form
        className="panel form-panel"
        onSubmit={(event) => {
          void upload(event);
        }}
      >
        <div className="form-grid">
          <label>
            图片或截图
            <input
              name="file"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              required
              disabled={locked || busy}
            />
          </label>
          <label>
            素材角色
            <select
              name="role"
              value={role}
              disabled={locked}
              onChange={(event) => setRole(event.target.value)}
            >
              <option value="evidence">事实证据 · 原图 / 截图</option>
              <option value="illustration">概念示意 · 解释内容</option>
              <option value="decoration">装饰画面 · 氛围内容</option>
            </select>
          </label>
          <label>
            来源地址
            <input
              name="source_url"
              type="url"
              placeholder="https://…（自己的实拍可留空）"
              disabled={locked}
            />
          </label>
          <label>
            授权与用途说明
            <input
              name="license_note"
              placeholder="例如：本人拍摄；已取得商业授权"
              disabled={locked}
            />
          </label>
        </div>
        <div className="inline-spread">
          <small className="muted">
            生成图片请标为概念示意或装饰，事实证据需有真实来源。
          </small>
          <button className="button primary" disabled={busy || locked}>
            {busy ? "正在上传…" : "上传素材"}
          </button>
        </div>
      </form>
      {!assets.length ? (
        <Empty title="还没有画面素材">
          上传真实截图、现场图片，或从有来源的内容开始。
        </Empty>
      ) : (
        <div className="asset-grid">
          {assets.map((asset) => (
            <article className="panel asset-card" key={asset.asset_id}>
              <a href={asset.url} target="_blank" rel="noreferrer">
                <img src={asset.url} alt={asset.name} loading="lazy" />
              </a>
              <div className="asset-card-content">
                <div className="inline-spread">
                  <strong>{asset.name}</strong>
                  <span className="badge">
                    {roleNames[asset.role] ?? asset.role}
                  </span>
                </div>
                <small className="muted">{formatBytes(asset.size_bytes)}</small>
                {asset.source_url ? (
                  <a
                    href={asset.source_url}
                    className="source-link"
                    target="_blank"
                    rel="noreferrer"
                  >
                    查看原始来源 ↗
                  </a>
                ) : (
                  <small className="muted">未附网页来源</small>
                )}
                <p className="license-note">
                  {asset.license_note || "授权与用途说明待补充"}
                </p>
                <a
                  className="quiet-link"
                  href={asset.url}
                  download={asset.name}
                >
                  下载原图 ↓
                </a>
              </div>
            </article>
          ))}
        </div>
      )}
    </fieldset>
  );
}
