# 摄影 UNKNOWN 通用修护计划

- 新增互斥 `restart-unknown --director-only`，沿用正式 `note` 传递最新摄影要求；明确可能用量确认仍为必需。旧请求默认字段不进入授权指纹。
- 在既有 SQLite 原子授权与命令锁内，绑定当前摄影 UNKNOWN 操作、provider、revision；仅创建一次新版 DRAFT，旧 UNKNOWN 与历史文件不变。
- 联合批准不能仅凭 confirm 存在继承。重建原 revision 的联合门输入投影，精确匹配真实回执的 dependency/policy 指纹；保留视觉来源、素材审计与原 metadata。投影不匹配即阻断。
- 绑定并保留已批准文案、Brief、真实视觉素材、选用音频、alignment、voice_guidance、audio_report 与文件 hash；授权后正常 run 再验，经过 audio_gate 直接进入摄影，随后仍停逐镜人审。
- 清理摄影/剪辑衍生引用，保留真实联合审批与飞书 Base；仅给摄影业务素材、证据结论和新 note，不提供恢复台账或审核流水。
- 合成回归覆盖新进程 CLI、幂等并发、批准投影、素材取舍/补采链、音频/文件篡改与正常节点路由。测试仅使用本 worktree 源码，无真实外部 API。

范围风险：历史联合门未存完整 subject；只接受能由现存文件与精确指纹证明的投影，不补造历史信息。不修改生产模型、超时、配音配置或真实任务。

## 本地验证记录

所有测试使用 `D:\remotion_video\.venv\Scripts\python.exe`，cwd 与 `PYTHONPATH` 均为
`D:\remotion_video_photography_unknown_recovery_20261014`，已回读 import 的源码路径。

- `tests/cli` 与 human_review、context、context_example_media、director_shot_review、director_model_contract、
  director_repair_receipt、director_demo_guard、director_review_catalog_drift、director_component_sets：
  364 passed in 179.84s。
- 最终 `tests/cli/test_director_only_restart.py`：47 passed in 74.97s；包含全新增改动、人工音频及历史音频、
  原文案批准继承、真实局部 WAV 时长校验、并发幂等、再恢复、voice-only、衍生引用清理与所有拒绝边界。
- `ruff check videoagents tests/cli`、`scripts/export-contracts.py --check`、
  `compileall -q videoagents worker`、`git diff --check` 均通过。
- 契约导出通过正式生成脚本更新；CLI help 已包含互斥 `--director-only`。

全部为合成流程/本机文件验证，没有真实 LLM、配音、飞书或生产运行。集成方继续完成 TypeScript/lint/bundle 检查。
