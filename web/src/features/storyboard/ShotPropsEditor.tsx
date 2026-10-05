import type { Shot } from "../../api/types";
import { isCommunityComponent } from "./timeline";

export function ShotPropsEditor({
  shot,
  update,
  disabled,
}: {
  shot: Shot;
  update: (props: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const props = shot.props;
  if (isCommunityComponent(shot.component_id))
    return (
      <small className="muted">
        该组件使用已验证的横版/竖版固定预设，不接受任意 props 或额外图片。
      </small>
    );
  const field = (key: string, label: string, max: number) => (
    <label key={key}>
      {label}
      <input
        value={String(props[key] ?? "")}
        maxLength={max}
        disabled={disabled}
        onChange={(event) => update({ ...props, [key]: event.target.value })}
      />
    </label>
  );
  if (shot.component_id === "title")
    return field("eyebrow", "标题上方短句", 48);
  if (shot.component_id === "keyword")
    return field("keyword", "强调关键词", 40);
  if (shot.component_id === "conclusion")
    return field("call_to_action", "结尾行动提示", 72);
  if (shot.component_id === "comparison")
    return (
      <div className="form-grid">
        {field("left_title", "左侧标题", 48)}
        {field("right_title", "右侧标题", 48)}
        {field("left_body", "左侧内容", 160)}
        {field("right_body", "右侧内容", 160)}
      </div>
    );
  if (shot.component_id === "image_focus")
    return (
      <div className="form-grid">
        {["focal_x", "focal_y"].map((key, index) => (
          <label key={key}>
            {index ? "垂直聚焦位置" : "水平聚焦位置"}（0–1）
            <input
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={String(props[key] ?? 0.5)}
              disabled={disabled}
              onChange={(event) =>
                update({ ...props, [key]: Number(event.target.value) })
              }
            />
          </label>
        ))}
      </div>
    );
  if (shot.component_id === "evidence") {
    const highlight = props.highlight as Record<string, number> | undefined;
    return (
      <>
        <label className="check-label">
          <input
            type="checkbox"
            checked={Boolean(highlight)}
            disabled={disabled}
            onChange={(event) => {
              if (event.target.checked)
                update({
                  highlight: { x: 0.1, y: 0.1, width: 0.8, height: 0.25 },
                });
              else update({});
            }}
          />
          突出图片中的证据区域
        </label>
        {highlight && (
          <div className="form-grid four-columns">
            {[
              ["x", "左边位置"],
              ["y", "上边位置"],
              ["width", "宽度"],
              ["height", "高度"],
            ].map(([key, label]) => (
              <label key={key}>
                {label}（0–1）
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={highlight[key]}
                  disabled={disabled}
                  onChange={(event) =>
                    update({
                      ...props,
                      highlight: {
                        ...highlight,
                        [key]: Number(event.target.value),
                      },
                    })
                  }
                />
              </label>
            ))}
          </div>
        )}
      </>
    );
  }
  if (shot.component_id === "data" || shot.component_id === "steps") {
    const isData = shot.component_id === "data";
    const items = (Array.isArray(props.items) ? props.items : []) as Record<
      string,
      string
    >[];
    const fields = isData
      ? ([
          ["label", "数据名称", 48],
          ["value", "真实数值", 40],
          ["detail", "说明", 64],
        ] as const)
      : ([
          ["title", "步骤标题", 48],
          ["body", "步骤说明", 96],
        ] as const);
    return (
      <div className="props-items">
        {items.map((item, index) => (
          <div className="props-item" key={index}>
            <span className="number-label">{index + 1}</span>
            {fields.map(([key, label, max]) => (
              <label key={key}>
                {label}
                <input
                  value={item[key] ?? ""}
                  maxLength={max}
                  disabled={disabled}
                  onChange={(event) =>
                    update({
                      ...props,
                      items: items.map((entry, position) =>
                        position === index
                          ? { ...entry, [key]: event.target.value }
                          : entry,
                      ),
                    })
                  }
                />
              </label>
            ))}
            <button
              className="text-button"
              disabled={disabled}
              onClick={() =>
                update({
                  ...props,
                  items: items.filter((_, position) => position !== index),
                })
              }
              aria-label="移除内容项"
            >
              ×
            </button>
          </div>
        ))}
        <button
          className="button secondary"
          disabled={disabled || items.length >= 4}
          onClick={() =>
            update({
              ...props,
              items: [
                ...items,
                isData
                  ? { label: "", value: "", detail: "" }
                  : { title: "", body: "" },
              ],
            })
          }
        >
          ＋ 添加{isData ? "数据" : "步骤"}
        </button>
        {isData && (
          <small className="muted">数值应来自文案中的已核验事实。</small>
        )}
      </div>
    );
  }
  return null;
}
