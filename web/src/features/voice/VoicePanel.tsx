import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type SetStateAction,
} from "react";
import { api, explainError } from "../../api/client";
import type { Job, RunAction } from "../../api/types";
import { Empty, Notice } from "../../components/ui";
import {
  buildAlignment,
  createAlignmentRows,
  type AlignmentRow,
} from "./alignment";

export function VoicePanel({
  job,
  refresh,
  onUpdate,
  run,
  locked,
  onDirty,
  paidGenerationBlocked,
}: {
  job: Job;
  refresh: () => Promise<unknown>;
  onUpdate: (job: Job) => void;
  run: (action: RunAction) => void;
  locked: boolean;
  onDirty: (dirty: boolean) => void;
  paidGenerationBlocked: boolean;
}) {
  const audios = job.assets.filter((asset) => asset.role === "audio");
  const [selectedAudio, setSelectedAudio] = useState(
    audios.at(-1)?.asset_id ?? "",
  );
  const [rows, setRowsState] = useState<AlignmentRow[]>(() =>
    createAlignmentRows(job.script),
  );
  const [note, setNote] = useState("");
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [dirty, setDirty] = useState(false);
  const [alignmentOrigin, setAlignmentOrigin] = useState("");
  const [duration, setDuration] = useState<number | null>(null);
  const [alignmentLoading, setAlignmentLoading] = useState(false);
  const dirtyRef = useRef(false);
  dirtyRef.current = dirty;
  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);
  const setRows = (value: SetStateAction<AlignmentRow[]>) => {
    setRowsState(value);
    setDirty(true);
    setVerified(false);
  };
  useEffect(() => {
    let active = true;
    void api
      .alignment(job.job_id)
      .then((data) => {
        if (active && !dirtyRef.current && data.asset_id)
          setSelectedAudio(data.asset_id);
      })
      .catch((cause: unknown) => {
        if (active) setError(explainError(cause));
      });
    return () => {
      active = false;
    };
  }, [job.job_id, audios.length]);
  useEffect(() => {
    if (!selectedAudio) return;
    let active = true;
    setAlignmentLoading(true);
    void api
      .alignment(job.job_id, selectedAudio)
      .then((data) => {
        if (!active) return;
        setDuration(data.duration_seconds);
        setAlignmentOrigin(data.alignment?.origin ?? "");
        if (dirtyRef.current) return;
        if (data.alignment) {
          setRowsState(
            data.alignment.segments.map((segment) => ({
              id: crypto.randomUUID(),
              segment_id: segment.segment_id,
              text: segment.text,
              start: String(segment.start_ms / 1000),
              end: String(segment.end_ms / 1000),
            })),
          );
          setNote(data.alignment.note);
        } else setRowsState(createAlignmentRows(job.script));
        setDirty(false);
        setVerified(false);
      })
      .catch((cause: unknown) => {
        if (active) setError(explainError(cause));
      })
      .finally(() => {
        if (active) setAlignmentLoading(false);
      });
    return () => {
      active = false;
    };
  }, [job.job_id, selectedAudio]);
  useEffect(() => {
    if (!selectedAudio && audios.length)
      setSelectedAudio(audios.at(-1)!.asset_id);
  }, [audios, selectedAudio]);
  const audio = audios.find((asset) => asset.asset_id === selectedAudio);
  const outputAudio =
    audios.find((asset) => asset.timeline_src === job.timeline?.audio_src) ??
    audio;
  const upload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || locked) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    data.set("role", "audio");
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const asset = await api.upload(job.job_id, data);
      setSelectedAudio(asset.asset_id);
      await refresh();
      form.reset();
      setSuccess("音频已导入。请试听，并填写实际测量的字幕时间。");
    } catch (cause) {
      setError(explainError(cause));
    } finally {
      setBusy(false);
    }
  };
  const saveAlignment = async () => {
    if (busy || locked) return;
    setError("");
    setSuccess("");
    if (!selectedAudio) {
      setError("请先上传或选择音频。");
      return;
    }
    if (!verified) {
      setError("请完成试听核对，并确认这些时间来自实际音频。");
      return;
    }
    try {
      const alignment = buildAlignment(rows, job.script, note);
      setBusy(true);
      const next = await api.saveAlignment(job, selectedAudio, alignment);
      onUpdate(next);
      setDirty(false);
      setAlignmentOrigin("manual");
      setSuccess("实测时间轴已保存，导演可以据此生成分镜。");
    } catch (cause) {
      setError(explainError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <fieldset
      className="feature-section editor-fieldset"
      disabled={locked || busy || alignmentLoading}
    >
      <div className="section-heading">
        <div>
          <h2>配音与试听</h2>
          <p>声音决定整条视频的节奏，分镜使用实际音频时间。</p>
        </div>
        <button
          className="button primary"
          disabled={locked || !job.script || paidGenerationBlocked}
          onClick={() => run("voice")}
        >
          生成 / 核验配音
        </button>
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {success && <Notice tone="success">{success}</Notice>}
      <div className="panel form-panel">
        <h3>已生成或导入的声音</h3>
        <p className="muted small">
          已上传音频时优先核验它的内容和时间轴。没有已有音频时，使用设置页配置的自有音色生成。
        </p>
        {outputAudio ? (
          <audio
            className="full-width"
            controls
            preload="metadata"
            src={outputAudio.url}
          />
        ) : (
          <Empty title="尚未生成配音">
            在设置页配置字节接口，也可以导入你自己录制的声音。
          </Empty>
        )}
      </div>
      <form
        className="panel form-panel"
        onSubmit={(event) => {
          void upload(event);
        }}
      >
        <h3>导入录音或已有配音</h3>
        <div className="form-grid">
          <label>
            音频文件
            <input
              type="file"
              name="file"
              accept="audio/wav,audio/mpeg,audio/mp4,audio/ogg,.wav,.mp3,.m4a,.ogg"
              required
              disabled={locked || busy}
            />
          </label>
          <label>
            音频授权说明
            <input
              name="license_note"
              placeholder="例如：本人的录音 / 本人音色生成"
              disabled={locked}
            />
          </label>
        </div>
        <div className="inline-spread">
          <small className="muted">导入音频会标记为用户上传。</small>
          <button className="button secondary" disabled={busy || locked}>
            {busy ? "正在上传…" : "导入音频"}
          </button>
        </div>
      </form>
      <div className="panel form-panel">
        <div className="inline-spread">
          <h3>实测字幕时间</h3>
          <button
            className="text-button"
            disabled={locked || !job.script}
            onClick={() => {
              setRows(createAlignmentRows(job.script));
              setVerified(false);
            }}
          >
            从已保存文案重新填写
          </button>
        </div>
        <p className="muted small">
          按音频逐句填写秒数；空白时间不会被自动估算。长段落可拆成多条字幕，拼接文字须与原文一致。
        </p>
        {alignmentOrigin && (
          <Notice>
            已读取保存的
            {alignmentOrigin === "manual"
              ? "人工实测"
              : alignmentOrigin === "provider"
                ? "配音服务"
                : "对齐服务"}
            时间轴
            {duration != null ? ` · 音频实测 ${duration.toFixed(3)} 秒` : ""}
            。修改后需重新试听确认。
          </Notice>
        )}
        <label>
          选择要对齐的音频
          <select
            value={selectedAudio}
            onChange={(event) => {
              setSelectedAudio(event.target.value);
              setVerified(false);
            }}
            disabled={locked}
          >
            <option value="">选择已上传音频</option>
            {audios.map((asset) => (
              <option key={asset.asset_id} value={asset.asset_id}>
                {asset.name}
              </option>
            ))}
          </select>
        </label>
        {audio && (
          <audio
            key={audio.asset_id}
            className="full-width"
            controls
            preload="metadata"
            src={audio.url}
          />
        )}
        {!rows.length ? (
          <Empty title="先保存口播文案">
            然后点击「从已保存文案重新填写」。
          </Empty>
        ) : (
          <div className="alignment-table">
            {rows.map((row, index) => (
              <div className="alignment-row" key={row.id}>
                <span className="number-label">{index + 1}</span>
                <label>
                  口播段落
                  <select
                    value={row.segment_id}
                    disabled={locked}
                    onChange={(event) =>
                      setRows((current) =>
                        current.map((item) =>
                          item.id === row.id
                            ? { ...item, segment_id: event.target.value }
                            : item,
                        ),
                      )
                    }
                  >
                    {job.script?.segments.map((segment, position) => (
                      <option
                        key={segment.segment_id}
                        value={segment.segment_id}
                      >
                        第 {position + 1} 段
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  字幕原文
                  <textarea
                    rows={2}
                    value={row.text}
                    maxLength={72}
                    disabled={locked}
                    onChange={(event) =>
                      setRows((current) =>
                        current.map((item) =>
                          item.id === row.id
                            ? { ...item, text: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </label>
                <label>
                  开始（秒）
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    value={row.start}
                    disabled={locked}
                    onChange={(event) =>
                      setRows((current) =>
                        current.map((item) =>
                          item.id === row.id
                            ? { ...item, start: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </label>
                <label>
                  结束（秒）
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    value={row.end}
                    disabled={locked}
                    onChange={(event) =>
                      setRows((current) =>
                        current.map((item) =>
                          item.id === row.id
                            ? { ...item, end: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </label>
                <button
                  aria-label={`删除第 ${index + 1} 条字幕`}
                  className="text-button"
                  disabled={locked}
                  onClick={() =>
                    setRows((current) =>
                      current.filter((item) => item.id !== row.id),
                    )
                  }
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        <button
          className="button secondary"
          disabled={locked || !job.script}
          onClick={() =>
            setRows((current) => [
              ...current,
              {
                id: crypto.randomUUID(),
                segment_id: job.script?.segments[0]?.segment_id ?? "",
                text: "",
                start: "",
                end: "",
              },
            ])
          }
        >
          ＋ 添加实测字幕
        </button>
        <label>
          对齐说明
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="例如：完整试听，逐句测量并核对文字"
            disabled={locked}
          />
        </label>
        <div className="inline-spread">
          <label className="check-label">
            <input
              type="checkbox"
              checked={verified}
              disabled={locked}
              onChange={(event) => setVerified(event.target.checked)}
            />
            我已试听核对，时间来自这份音频的实际测量
          </label>
          <button
            className="button primary"
            disabled={busy || locked || !audio || !rows.length}
            onClick={() => {
              void saveAlignment();
            }}
          >
            {busy ? "正在保存…" : "保存实测时间"}
          </button>
        </div>
      </div>
    </fieldset>
  );
}
