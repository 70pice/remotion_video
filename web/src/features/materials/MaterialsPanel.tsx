import { useEffect, useMemo, useState } from "react";
import { api, explainError } from "../../api/client";
import type { Job } from "../../api/types";
import { Empty, formatBytes, Notice } from "../../components/ui";

interface ResearchSource {
  url: string;
  final_url?: string;
  title?: string;
  snippet?: string;
  platform?: string;
  backend?: string;
  text?: string;
  artifact_url?: string;
  asset_ids?: string[];
}

interface ResearchVisual {
  asset_id: string;
  kind?: string;
  source_url?: string;
  title?: string;
  knowledge_excerpt?: string;
  license_status?: string;
}

export interface ResearchPackage {
  schema_version?: string;
  status?: string;
  query?: string;
  tools?: Array<Record<string, unknown>>;
  search_results?: Array<Record<string, unknown>>;
  sources?: ResearchSource[];
  visuals?: ResearchVisual[];
  failures?: Array<Record<string, unknown>>;
  capture_notes?: Array<Record<string, unknown>>;
  collected_at?: string;
}

const toolStatuses: Record<string, string> = {
  ok: "检索成功", error: "检索失败", unavailable: "不可用", skipped: "已跳过",
};
const failureReasons: Record<string, string> = {
  search_budget_exhausted: "检索预算已用完",
  search_not_configured: "检索服务未配置",
  google_requires_opencli_or_google_cse: "Google 需要 OpenCLI 或 Google CSE",
};

function sourceTitle(source: ResearchSource): string {
  if (source.title) return source.title;
  try { return new URL(source.url).hostname; } catch { return source.url; }
}

export function MaterialsContent({ job, research }: { job: Job; research: ResearchPackage }) {
  const visualAssets = job.assets.filter((asset) =>
    research.visuals?.some((visual) => visual.asset_id === asset.asset_id),
  );
  return <>
    <div className="materials-summary">
      <span className="badge">{research.sources?.length ?? 0} 个已读取来源</span>
      <span className="badge">{visualAssets.length} 个画面素材</span>
      <span className="muted small">检索词：{research.query || job.brief.topic}</span>
    </div>
    {!!research.tools?.length && <div className="materials-block">
      <h3>平台检索</h3>
      <div className="source-list">{research.tools.map((tool, index) => {
        const status = String(tool.status ?? "unknown");
        const reason = String(tool.error ?? "");
        return <article className="source-card" key={index}>
          <strong>{String(tool.label ?? tool.platform ?? "平台")} · {toolStatuses[status] ?? status}</strong>
          <p className="muted small">检索方式：{String(tool.backend ?? "未记录")}
            {typeof tool.results_count === "number" && ` · ${tool.results_count} 条命中`}
            {reason && ` · ${failureReasons[reason] ?? reason}`}
          </p>
        </article>;
      })}</div>
    </div>}
    {!!visualAssets.length && <div className="materials-block">
      <h3>图片与截图</h3>
      <div className="visual-grid">{visualAssets.map((asset) => {
        const visual = research.visuals?.find((item) => item.asset_id === asset.asset_id);
        return <article className="visual-card" key={asset.asset_id}>
          <a href={asset.url} target="_blank" rel="noreferrer">
            <img src={asset.url} alt={asset.name} loading="lazy" />
          </a>
          <strong>{visual?.kind === "screenshot" ? "网页截图" : "来源图片"} · {visual?.title || asset.name}</strong>
          <small>{formatBytes(asset.size_bytes)} · 再利用许可待审核</small>
          {visual?.knowledge_excerpt && <p className="muted small">{visual.knowledge_excerpt.slice(0, 180)}</p>}
          {(visual?.source_url || asset.source_url) && <a href={visual?.source_url || asset.source_url} target="_blank" rel="noreferrer">查看素材出处</a>}
        </article>;
      })}</div>
    </div>}
    {!!research.sources?.length && <div className="materials-block">
      <h3>已读取来源</h3>
      <p className="muted small">搜索摘要用于发现线索。以下正文已读取并保存，具体事实仍由文案审查核验。</p>
      <div className="source-list">{research.sources.map((source, index) => <article className="source-card" key={`${source.url}-${index}`}>
        <div className="inline-spread">
          <strong>{sourceTitle(source)}</strong>
          <span className="badge">{source.platform || "人工来源"}</span>
        </div>
        <p>{source.text?.slice(0, 180) || source.snippet || "已保存来源正文。"}</p>
        <a href={source.url} target="_blank" rel="noreferrer">{source.final_url || source.url}</a>
        {source.artifact_url && <p><a href={source.artifact_url} download>下载来源快照</a></p>}
      </article>)}</div>
    </div>}
    {!!(research.failures?.length || research.capture_notes?.length) && <div className="materials-block">
      <h3>未完成项</h3>
      {[...(research.failures ?? []), ...(research.capture_notes ?? [])].map((item, index) => <p className="muted small" key={index}>
        {String(item.url ?? item.platform ?? "来源")} · {String(item.reason ?? "未读取")}
      </p>)}
    </div>}
  </>;
}

export function MaterialsPanel({ job }: { job: Job }) {
  const researchArtifact = useMemo(
    () =>
      [...job.artifacts]
        .reverse()
        .find(
          (artifact) =>
            artifact.kind === "research" && artifact.revision === job.revision,
        ),
    [job.artifacts, job.revision],
  );
  const [research, setResearch] = useState<ResearchPackage | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setResearch(null);
    setError("");
    if (!researchArtifact) return () => undefined;
    void api
      .artifactJson<ResearchPackage>(researchArtifact.url)
      .then((value) => {
        if (active) setResearch(value);
      })
      .catch((cause) => {
        if (active) setError(explainError(cause));
      });
    return () => {
      active = false;
    };
  }, [researchArtifact]);
  return (
    <section className="panel materials-panel">
      <div className="inline-spread">
        <div>
          <h2>素材研究</h2>
          <p className="muted small">
            素材节点采集公开来源、截图和候选图片，后续文案与导演只引用这些已登记素材。
          </p>
        </div>
        {researchArtifact && (
          <a className="button secondary small" href={researchArtifact.url} download={researchArtifact.name}>
            下载研究包
          </a>
        )}
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {!researchArtifact ? (
        <Empty title="还没有素材研究包">
          开始制作后会先进入素材节点；也可以先上传人工素材。
        </Empty>
      ) : error ? null : !research ? (
        <div className="loading">正在读取素材研究包…</div>
      ) : (
        <MaterialsContent job={job} research={research} />
      )}
    </section>
  );
}
