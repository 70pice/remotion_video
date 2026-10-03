import { Component, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { Health } from "../api/types";
import { Notice } from "../components/ui";
import { JobsPage } from "../pages/JobsPage";
import { CreateJobPage } from "../pages/CreateJobPage";
import { JobWorkspacePage } from "../pages/JobWorkspacePage";
import { ComponentLibraryPage } from "../pages/ComponentLibraryPage";
import { SettingsPage } from "../pages/SettingsPage";
import { useRoute } from "./router";

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  render() {
    if (this.state.error)
      return (
        <Notice tone="error">
          页面无法正常显示。任务仍保存在后端。
          <button className="text-button" onClick={() => location.reload()}>
            重新打开
          </button>
        </Notice>
      );
    return this.props.children;
  }
}

export function App() {
  const path = useRoute();
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const data = await api.health();
        if (active) setHealth(data);
      } catch {
        if (active) setHealth(null);
      }
    };
    void check();
    const timer = setInterval(() => {
      void check();
    }, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  const jobMatch = path.match(/^\/jobs\/([^/]+)$/);
  let page: ReactNode = <JobsPage />;
  if (path === "/create") page = <CreateJobPage />;
  else if (path === "/catalog") page = <ComponentLibraryPage />;
  else if (path === "/settings") page = <SettingsPage />;
  else if (jobMatch)
    page = (
      <JobWorkspacePage
        key={jobMatch[1]}
        jobId={decodeURIComponent(jobMatch[1])}
      />
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a href="#/" className="brand" aria-label="VideoAgents 首页">
          <span className="brand-mark">
            V<span>↗</span>
          </span>
          <div>
            VideoAgents<small>创意，开始协作。</small>
          </div>
        </a>
        <div className="sidebar-label">制作空间</div>
        <nav aria-label="主导航">
          <a className={path === "/" || jobMatch ? "active" : ""} href="#/">
            <span>▦</span>视频任务
          </a>
          <a className={path === "/create" ? "active" : ""} href="#/create">
            <span>＋</span>新建视频
          </a>
          <a className={path === "/catalog" ? "active" : ""} href="#/catalog">
            <span>◈</span>画面组件库
          </a>
        </nav>
        <div className="sidebar-note">
          <span>五个角色，一条时间轴。</span>
          <p>
            编剧 → 配音 → 导演
            <br />
            剪辑 → 审核
          </p>
        </div>
        <div className="sidebar-bottom">
          <a className={path === "/settings" ? "active" : ""} href="#/settings">
            <span>⚙</span>系统设置
          </a>
          <div className="service-state">
            <span
              className={`connection-dot ${health?.worker_alive ? "connected" : ""}`}
            />
            <div>
              {!health
                ? "服务未连接"
                : health.worker_alive
                  ? "后台执行进程在线"
                  : "API 在线 · 后台未启动"}
              <small>
                {health ? `v${health.version}` : "启动服务后自动恢复"}
              </small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>视频制作工作台</span>
          <span className="topbar-right">
            <span className="local-pill">本机工作空间</span>
            <span className="avatar">我</span>
          </span>
        </header>
        <main key={path}>
          <ErrorBoundary>{page}</ErrorBoundary>
        </main>
        <footer>文案、素材、声音与成片，保存在每个任务的独立版本中。</footer>
      </div>
    </div>
  );
}
