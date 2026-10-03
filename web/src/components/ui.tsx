import type { ReactNode } from "react";

export const statusLabels: Record<string, string> = {
  DRAFT: "草稿",
  QUEUED: "排队中",
  RUNNING: "制作中",
  NEEDS_INPUT: "待补充",
  NEEDS_HUMAN: "待复核",
  READY_FOR_PUBLISH: "审核通过",
  REJECTED: "未通过",
  FAILED: "执行失败",
  CANCELLED: "已取消",
  UNKNOWN: "受理情况待确认",
};
export const stageLabels: Record<string, string> = {
  idle: "未开始",
  script: "编剧",
  voice: "配音",
  director: "导演",
  render: "剪辑",
  review: "审核",
  complete: "完成",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge status-${status.toLowerCase()}`}>
      {statusLabels[status] ?? status}
    </span>
  );
}

export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "error" | "success";
}) {
  return (
    <div
      className={`notice notice-${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}

export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-symbol">◇</span>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}

export function PageHeading({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        {children && <p>{children}</p>}
      </div>
      {action}
    </div>
  );
}

export function formatDate(date: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
}

export function formatBytes(bytes: number): string {
  return bytes > 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
