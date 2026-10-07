import { useEffect, useState } from "react";
import { api, explainError } from "../api/client";
import type { Job } from "../api/types";
import { displayedStatus, isPublishReady } from "../api/jobStatus";
import {
  Empty,
  formatDate,
  Notice,
  PageHeading,
  stageLabels,
  StatusBadge,
} from "../components/ui";

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  useEffect(() => {
    let mounted = true;
    const refresh = async () => {
      try {
        const data = await api.jobs();
        if (mounted) {
          setJobs(data);
          setLoaded(true);
          setError("");
        }
      } catch (cause) {
        if (mounted) {
          setError(explainError(cause));
          setLoaded(true);
        }
      }
    };
    void refresh();
    const timer = setInterval(() => {
      void refresh();
    }, 5000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);
  const running = jobs.filter((job) =>
    ["RUNNING", "QUEUED"].includes(job.status),
  ).length;
  const waiting = jobs.filter((job) =>
    ["NEEDS_INPUT", "NEEDS_HUMAN", "FAILED"].includes(job.status),
  ).length;
  const ready = jobs.filter(isPublishReady).length;
  const visible = jobs.filter(
    (job) =>
      filter === "all" ||
      (filter === "active"
        ? ["RUNNING", "QUEUED"].includes(job.status)
        : filter === "waiting"
          ? ["NEEDS_INPUT", "NEEDS_HUMAN", "FAILED"].includes(job.status)
          : isPublishReady(job)),
  );
  return (
    <>
      <PageHeading
        eyebrow="YOUR PRODUCTION DESK"
        title="视频任务"
        action={
          <a className="button primary" href="#/create">
            ＋ 新建视频
          </a>
        }
      >
        从一个想法，到一条可交付的视频。
      </PageHeading>
      {error && <Notice tone="error">{error}</Notice>}
      <div className="stats-grid">
        <div className="stat-card">
          <span>全部任务</span>
          <strong>{jobs.length}</strong>
          <small>每条视频独立保存</small>
        </div>
        <div className="stat-card">
          <span>正在制作</span>
          <strong>{running}</strong>
          <small>刷新页面后继续</small>
        </div>
        <div className="stat-card">
          <span>需要你处理</span>
          <strong>{waiting}</strong>
          <small>补充素材或复核</small>
        </div>
        <div className="stat-card">
          <span>审核通过</span>
          <strong>{ready}</strong>
          <small>查看交付与下载</small>
        </div>
      </div>
      <div className="panel">
        <div className="panel-toolbar">
          <h2>制作记录</h2>
          <div className="segmented">
            {[
              ["all", "全部"],
              ["active", "制作中"],
              ["waiting", "待处理"],
              ["ready", "已通过"],
            ].map(([value, label]) => (
              <button
                key={value}
                onClick={() => setFilter(value)}
                className={filter === value ? "selected" : ""}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {!loaded ? (
          <Empty title="正在读取任务…" />
        ) : !visible.length ? (
          <Empty
            title={jobs.length ? "这里暂时没有任务" : "开始你的第一条视频"}
          >
            提供主题或本期创作方向，让编剧、配音、导演和剪辑依次协作。
          </Empty>
        ) : (
          <div className="job-list">
            {visible.map((job) => (
              <a
                key={job.job_id}
                className="job-row"
                href={`#/jobs/${job.job_id}`}
              >
                <div className="job-icon">
                  {job.brief.width > job.brief.height ? "▰" : "▯"}
                </div>
                <div className="job-primary">
                  <h3>
                    {job.script?.title ||
                      job.brief.topic ||
                      (job.brief.creative_direction || job.brief.script_text).slice(0, 30)}
                  </h3>
                  <p>
                    {job.brief.platform} · {job.brief.target_seconds} 秒 ·{" "}
                    {job.brief.usage === "commercial"
                      ? "商业用途"
                      : job.brief.usage === "personal"
                        ? "个人用途"
                        : "用途待确认"}
                  </p>
                </div>
                <div className="job-state">
                  <StatusBadge status={displayedStatus(job)} />
                  <small>
                    {stageLabels[job.stage] ?? job.stage}
                    {job.progress != null
                      ? ` · ${Math.round(job.progress * 100)}%`
                      : ""}
                  </small>
                </div>
                <time>{formatDate(job.updated_at)}</time>
                <span className="arrow">↗</span>
              </a>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
