import { useEffect, useState } from "react";
import { api, explainError } from "../api/client";
import type { ComponentEntry } from "../api/types";
import { Empty, Notice, PageHeading } from "../components/ui";

export function ComponentLibraryPage() {
  const [catalog, setCatalog] = useState<ComponentEntry[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("production");
  useEffect(() => {
    let active = true;
    void api
      .catalog()
      .then((items) => {
        if (active) {
          setCatalog(items);
          setLoaded(true);
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(explainError(cause));
          setLoaded(true);
        }
      });
    return () => {
      active = false;
    };
  }, []);
  const filtered = catalog.filter(
    (entry) =>
      (filter !== "production" || entry.production_ready) &&
      `${entry.name} ${entry.description} ${entry.use_case}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeading eyebrow="VISUAL TOOLKIT" title="画面组件库">
        按表达目的选画面，让每个镜头服务于你的内容。
      </PageHeading>
      {error && <Notice tone="error">{error}</Notice>}
      <div className="panel-toolbar catalog-toolbar">
        <div className="segmented">
          <button
            className={filter === "production" ? "selected" : ""}
            onClick={() => setFilter("production")}
          >
            可用于生产 ·{" "}
            {catalog.filter((item) => item.production_ready).length}
          </button>
          <button
            className={filter === "all" ? "selected" : ""}
            onClick={() => setFilter("all")}
          >
            全部目录 · {catalog.length}
          </button>
        </div>
        <input
          aria-label="搜索组件"
          placeholder="搜索名称、场景…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      {!loaded ? (
        <Empty title="正在读取组件目录…" />
      ) : !filtered.length ? (
        <Empty title="没有匹配的组件" />
      ) : (
        <div className="catalog-grid">
          {filtered.map((entry) => (
            <article className="panel catalog-card" key={entry.component_id}>
              <div className="component-preview">
                {entry.preview_url ? (
                  <img
                    src={entry.preview_url}
                    alt={entry.name}
                    loading="lazy"
                  />
                ) : (
                  <>
                    <span>{entry.production_ready ? "◈" : "◇"}</span>
                    <strong>{entry.name}</strong>
                    <small>{entry.orientation}</small>
                  </>
                )}
              </div>
              <div className="catalog-card-content">
                <div className="inline-spread">
                  <h3>{entry.name}</h3>
                  <span
                    className={`badge ${entry.production_ready ? "status-ready_for_publish" : ""}`}
                  >
                    {entry.production_ready ? "生产可用" : "演示参考"}
                  </span>
                </div>
                <p>{entry.description}</p>
                <p className="small">
                  适用于：{entry.use_case || "查看组件说明"}
                </p>
                <div className="license-note">
                  {entry.license_note || "授权说明待补充"}
                </div>
                {!entry.production_ready && (
                  <small className="muted">
                    尚未适配生产参数，工作台暂不可选择。
                  </small>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
