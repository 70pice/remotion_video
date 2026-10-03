import type { Job, Script, ScriptDiscussion } from "../../api/types";
import { Notice } from "../../components/ui";

const statusText: Record<ScriptDiscussion["status"], string> = {
  DISABLED: "未启用",
  DISCUSSING: "讨论中",
  APPROVED: "文案讨论通过",
  EXHAUSTED: "达到审查轮数上限",
};

const categoryText: Record<string, string> = {
  fact: "事实",
  logic: "逻辑",
  hook: "开头吸引力",
  clarity: "表达清晰度",
  visual: "画面表达",
  rights: "版权与权利",
};

function scriptText(script: Script): string {
  const segments = script.segments
    .map((segment, index) => {
      const screen = segment.screen_text
        ? `\n画面文字：${segment.screen_text}`
        : "";
      const sources = segment.source_refs.length
        ? `\n来源：${segment.source_refs.join("、")}`
        : "\n来源：未填写";
      const assets = segment.asset_ids.length
        ? `\n素材：${segment.asset_ids.join("、")}`
        : "\n素材：未绑定";
      return `${index + 1}. ${segment.narration}${screen}${sources}${assets}`;
    })
    .join("\n\n");
  return `标题：${script.title}\n\n${segments}`;
}

export function ScriptDiscussionPanel({ job }: { job: Job }) {
  const discussion = job.script_discussion;
  if (!discussion) return null;

  const stale = discussion.revision !== job.revision;
  const completedCritiques = discussion.rounds.filter(
    (round) => round.critique !== null,
  ).length;
  const remaining =
    discussion.status === "DISCUSSING"
      ? Math.max(0, discussion.max_rounds - completedCritiques)
      : 0;

  return (
    <section
      className={`panel script-discussion-panel ${stale ? "script-discussion-stale" : ""}`}
      aria-labelledby="script-discussion-title"
    >
      <div className="section-heading">
        <div>
          <h2 id="script-discussion-title">文案讨论</h2>
          <p>
            编剧和文案审查交替修改稿件；这里只显示文案阶段结论，不代表最终发布资格。
          </p>
        </div>
        <span className={`badge discussion-${discussion.status.toLowerCase()}`}>
          {stale
            ? `历史第 ${discussion.revision} 版`
            : statusText[discussion.status]}
        </span>
      </div>
      {stale ? (
        <Notice>
          这是第 {discussion.revision} 版的讨论记录；当前任务是第 {job.revision}{" "}
          版，不把历史通过状态当作当前文案通过。
        </Notice>
      ) : discussion.status === "EXHAUSTED" ? (
        <Notice tone="error">
          文案审查已达到 {discussion.max_rounds} 轮上限，仍需要修改；流程会等待补充或人工处理。
        </Notice>
      ) : discussion.status === "DISCUSSING" ? (
        <Notice>
          文案讨论正在进行，已完成 {completedCritiques} 轮审查，剩余 {remaining}{" "}
          轮审查额度。
        </Notice>
      ) : discussion.status === "APPROVED" ? (
        <Notice>
          文案讨论已通过；后续仍需来源与素材检查，最终发布资格由审核节点和人工复核决定。
        </Notice>
      ) : null}
      <div className="discussion-meta">
        <span>任务版本：第 {discussion.revision} 版</span>
        <span>最大轮数：{discussion.max_rounds}</span>
        <span>已审查：{completedCritiques}</span>
        <span>稿件轮数：{discussion.rounds.length}</span>
      </div>
      {discussion.rounds.length ? (
        <div className="discussion-rounds">
          {discussion.rounds.map((round) => (
            <article className="discussion-round" key={round.round}>
              <div className="inline-spread">
                <h3>第 {round.round} 轮</h3>
                <span className="muted small">
                  {round.critique
                    ? round.critique.decision === "APPROVE"
                      ? "审查建议：通过"
                      : "审查建议：修改"
                    : "等待审查"}
                </span>
              </div>
              {round.response && (
                <div className="discussion-response">
                  <strong>编剧回应</strong>
                  <p>{round.response}</p>
                </div>
              )}
              {round.critique ? (
                <div className="discussion-critique">
                  <strong>审查总结</strong>
                  <p>{round.critique.summary}</p>
                  {round.critique.strengths.length > 0 && (
                    <>
                      <strong>优点</strong>
                      <ul>
                        {round.critique.strengths.map((strength, index) => (
                          <li key={`${round.round}-strength-${index}`}>
                            {strength}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                  {round.critique.issues.length > 0 && (
                    <>
                      <strong>需要修改</strong>
                      <ul className="discussion-issues">
                        {round.critique.issues.map((issue, index) => (
                          <li key={`${round.round}-issue-${index}`}>
                            <span className="issue-category">
                              {categoryText[issue.category] ?? issue.category}
                            </span>
                            {issue.segment_id && (
                              <span className="muted small">
                                段落：{issue.segment_id}
                              </span>
                            )}
                            <p>{issue.concern}</p>
                            <p className="muted">建议：{issue.suggestion}</p>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              ) : (
                <p className="muted">这一轮还没有审查结果。</p>
              )}
              <details>
                <summary>查看本轮完整稿件</summary>
                <pre className="script-discussion-script">
                  {scriptText(round.script)}
                </pre>
              </details>
            </article>
          ))}
        </div>
      ) : (
        <p className="muted">还没有讨论轮次。</p>
      )}
    </section>
  );
}
