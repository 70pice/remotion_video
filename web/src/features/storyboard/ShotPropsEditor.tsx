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
  const setProp = (key: string, value: unknown) => {
    const next = { ...props };
    if (value === undefined) delete next[key];
    else next[key] = value;
    update(next);
  };
  const cueInput = (value: unknown, change: (value: number | undefined) => void) => (
    <input
      type="number"
      min="0"
      max={Math.max(0, shot.end_frame - shot.start_frame - 15)}
      step="1"
      value={String(value ?? "")}
      placeholder="沿用开场动画"
      disabled={disabled}
      onChange={(event) => change(event.target.value === "" ? undefined : Number(event.target.value))}
    />
  );
  if (isCommunityComponent(shot.component_id)) {
    const items = (Array.isArray(props.items) ? props.items : []) as string[];
    const metric = (props.metric && typeof props.metric === "object" && !Array.isArray(props.metric)
      ? props.metric
      : {}) as Record<string, unknown>;
    const crop = props.asset_crop as Record<string, number> | undefined;
    return (
      <div className="props-items">
        <div className="form-grid">
          <label>
            内容槽位
            <select
              value={String(props.content_mode ?? "auto")}
              disabled={disabled}
              onChange={(event) => setProp("content_mode", event.target.value === "auto" ? undefined : event.target.value)}
            >
              <option value="auto">自动</option>
              <option value="media">素材</option>
              <option value="list">短列表</option>
              <option value="metric">指标</option>
            </select>
          </label>
          <label>
            素材填充
            <select
              value={String(props.asset_fit ?? "contain")}
              disabled={disabled}
              onChange={(event) => setProp("asset_fit", event.target.value === "contain" ? undefined : event.target.value)}
            >
              <option value="contain">完整显示 contain</option>
              <option value="cover">铺满裁切 cover</option>
            </select>
          </label>
        </div>
        <label className="check-label">
          <input
            type="checkbox"
            checked={Boolean(crop)}
            disabled={disabled}
            onChange={(event) => {
              if (event.target.checked)
                setProp("asset_crop", { x: 0, y: 0, width: 1, height: 1 });
              else setProp("asset_crop", undefined);
            }}
          />
          手动裁切素材区域
        </label>
        {crop && (
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
                  value={crop[key]}
                  disabled={disabled}
                  onChange={(event) =>
                    setProp("asset_crop", {
                      ...crop,
                      [key]: Number(event.target.value),
                    })
                  }
                />
              </label>
            ))}
          </div>
        )}
        <div className="form-grid">
          <label>
            视频起始秒
            <input
              type="number"
              min="0"
              step="0.01"
              value={String(props.start_seconds ?? "")}
              disabled={disabled}
              onChange={(event) =>
                setProp("start_seconds", event.target.value === "" ? undefined : Number(event.target.value))
              }
            />
          </label>
          <label>
            视频结束秒
            <input
              type="number"
              min="0"
              step="0.01"
              value={String(props.end_seconds ?? "")}
              disabled={disabled}
              onChange={(event) =>
                setProp("end_seconds", event.target.value === "" ? undefined : Number(event.target.value))
              }
            />
          </label>
        </div>
        <div className="props-items">
          {items.map((item, index) => (
            <div className="props-item" key={index}>
              <span className="number-label">{index + 1}</span>
              <label>
                短列表项
                <input
                  value={item}
                  maxLength={64}
                  disabled={disabled}
                  onChange={(event) =>
                    setProp("items", items.map((entry, position) => position === index ? event.target.value : entry))
                  }
                />
              </label>
              <button
                className="text-button"
                disabled={disabled}
                onClick={() => setProp("items", items.filter((_, position) => position !== index))}
                aria-label="移除内容项"
              >
                ×
              </button>
            </div>
          ))}
          <button
            className="button secondary"
            disabled={disabled || items.length >= 4}
            onClick={() => setProp("items", [...items, ""])}
          >
            ＋ 添加短列表项
          </button>
        </div>
        <div className="form-grid">
          {[
            ["label", "指标名称", 48],
            ["value", "指标数值", 40],
            ["detail", "指标说明", 64],
          ].map(([key, label, max]) => (
            <label key={key}>
              {label}
              <input
                value={String(metric[key] ?? "")}
                maxLength={Number(max)}
                disabled={disabled}
                onChange={(event) => {
                  const next = {...metric, [key]: event.target.value};
                  if (!next.label && !next.value && !next.detail) setProp("metric", undefined);
                  else setProp("metric", next);
                }}
              />
            </label>
          ))}
        </div>
        <small className="muted">社区预设只接受当前任务素材和这些安全槽位，不支持任意 CSS、URL 或组件私有参数。</small>
      </div>
    );
  }
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
  const cropFields = (crop: Record<string, number>, change: (crop: Record<string, number>) => void) => (
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
            value={crop[key]}
            disabled={disabled}
            onChange={(event) =>
              change({
                ...crop,
                [key]: Number(event.target.value),
              })
            }
          />
        </label>
      ))}
    </div>
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
        <label>
          右侧出现帧（镜头内，可留空）
          {cueInput(props.right_reveal_frame, (value) => setProp("right_reveal_frame", value))}
        </label>
      </div>
    );
  if (shot.component_id === "image_focus") {
    const crop = props.crop as Record<string, number> | undefined;
    return (
      <div className="props-items">
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
        <label className="check-label">
          <input
            type="checkbox"
            checked={Boolean(crop)}
            disabled={disabled}
            onChange={(event) => {
              if (event.target.checked)
                setProp("crop", { x: 0, y: 0, width: 1, height: 1 });
              else setProp("crop", undefined);
            }}
          />
          手动裁切图片区域
        </label>
        {crop && cropFields(crop, (next) => setProp("crop", next))}
      </div>
    );
  }
  if (shot.component_id === "video") {
    const crop = props.crop as Record<string, number> | undefined;
    return (
      <div className="props-items">
        <div className="form-grid">
          <label>
            视频起始秒
            <input
              type="number"
              min="0"
              step="0.01"
              value={String(props.start_seconds ?? 0)}
              disabled={disabled}
              onChange={(event) =>
                setProp("start_seconds", Number(event.target.value))
              }
            />
          </label>
          <label>
            视频结束秒（可留空）
            <input
              type="number"
              min="0"
              step="0.01"
              value={String(props.end_seconds ?? "")}
              disabled={disabled}
              onChange={(event) =>
                setProp(
                  "end_seconds",
                  event.target.value === ""
                    ? undefined
                    : Number(event.target.value),
                )
              }
            />
          </label>
          <label>
            填充方式
            <select
              value={String(props.fit ?? "contain")}
              disabled={disabled}
              onChange={(event) => setProp("fit", event.target.value)}
            >
              <option value="contain">完整显示 contain</option>
              <option value="cover">铺满裁切 cover</option>
            </select>
          </label>
        </div>
        <label className="check-label">
          <input
            type="checkbox"
            checked={Boolean(crop)}
            disabled={disabled}
            onChange={(event) => {
              if (event.target.checked)
                setProp("crop", { x: 0, y: 0, width: 1, height: 1 });
              else setProp("crop", undefined);
            }}
          />
          手动设置视频裁剪框
        </label>
        {crop && cropFields(crop, (next) => setProp("crop", next))}
      </div>
    );
  }
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
      unknown
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
        {!isData && (
          <label>
            步骤布局
            <select value={String(props.layout ?? "cards")} disabled={disabled}
              onChange={(event) => setProp("layout", event.target.value === "cards" ? undefined : event.target.value)}>
              <option value="cards">步骤卡片</option>
              <option value="flow">连接流程</option>
            </select>
          </label>
        )}
        {items.map((item, index) => (
          <div className="props-item" key={index}>
            <span className="number-label">{index + 1}</span>
            {fields.map(([key, label, max]) => (
              <label key={key}>
                {label}
                <input
                  value={String(item[key] ?? "")}
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
            <label>
              出现帧（镜头内，可留空）
              {cueInput(item.reveal_frame, (value) => update({
                ...props,
                items: items.map((entry, position) => {
                  if (position !== index) return entry;
                  const next = {...entry};
                  if (value === undefined) delete next.reveal_frame;
                  else next.reveal_frame = value;
                  return next;
                }),
              }))}
            </label>
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
        <small className="muted">出现帧按真实口播顺序设置；最后保留 15 帧让内容完整出现。</small>
      </div>
    );
  }
  return null;
}
