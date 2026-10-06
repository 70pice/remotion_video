# VideoAgents implementation contract

Approved design: `.omx/plans/videoagents-langgraph-design-2026-10-03.md`. Frontend MUST be React. This document defines shared interfaces for parallel implementation; production and test outputs must be distinguishable.

## Ownership

- Backend lane: `server/`, `worker/`, `videoagents/`, `tests/api/`, `tests/videoagents/`, `tests/worker/`. Own canonical Python models, persistence, providers and all API routes. Export schemas through a leader-owned script later.
- Frontend lane: `web/` only. Do not change root package.json or lockfiles. Use React 19 already present; dependency requirements returned to leader.
- Render lane: `src/video-production/`, `scripts/render-timeline.mjs`, the minimal registration change to `src/Root.tsx`. Do not touch existing demo/card implementations or package files.
- Leader: root dependency/configuration files, scripts/launchers, generated contracts, docs, fixtures/e2e and integration.

## Stable HTTP interface

All routes under `/api`. JSON errors use `{"detail":"human readable reason"}`. Mutation responses return the complete updated job except settings and upload. Avoid wrappers around list results.

- `GET /health` => `{status:"ok", worker_alive:boolean, version:string}`.
- `GET /session` => `{csrf_token:string}` plus a HttpOnly SameSite=Strict `videoagents_session` cookie. All protected reads require the session, and mutations additionally require `X-CSRF-Token`. Browser requests include credentials; API checks allowed local Host and Origin.
- `GET /jobs` => `Job[]`; `POST /jobs` with Brief => Job.
- `GET /jobs/{job_id}` => Job.
- `PATCH /jobs/{job_id}/draft` with `{base_revision:number, brief?:Brief, script?:Script, timeline?:Timeline}` => Job; stale revision returns 409. Revision changes invalidate dependent outputs and prior release.
- `POST /jobs/{job_id}/runs` with `{base_revision:number, action:"produce"|"voice"|"storyboard"|"preview"|"final"|"review", idempotency_key:string}` => Job (202). Duplicate identical commands never enqueue twice; changed payload with same key is 409.
- `POST /jobs/{job_id}/cancel` => Job.
- `POST /jobs/{job_id}/resume` with `{base_revision:number, pending_token:string, decision:"confirm"|"revise"|"cancel", note?:string, idempotency_key:string}` => Job. The token binds the specific pending interrupt, including changes within the same revision. Human confirmation only clears appropriate human findings; never bypasses hard errors. A consumed command cannot answer a later interrupt after worker recovery.
- `GET /jobs/{job_id}/events?after=<event_id>` => SSE events (`id`, `event: progress`, JSON payload). Persist IDs and reconnect replay. Polling the Job is always supported.
- `POST /jobs/{job_id}/assets` multipart: `file`, `role` (evidence/illustration/decoration/audio), optional `source_url`, `license_note`, optional `alignment` JSON. Return Asset. Uploaded WAV/audio is imported voice, not claimed cloned/generated.
- `GET /jobs/{job_id}/alignment?asset_id=<id>` => `{asset_id:string|null, alignment:Alignment|null, duration_seconds:number|null}` for the selected or currently active audio.
- `POST /jobs/{job_id}/alignment` with `{base_revision:number, asset_id:string, alignment:Alignment}` => Job; binds the measured alignment to that audio and invalidates dependent outputs. Empty/omitted audio hash is server-bound; a supplied nonempty hash must match.
- `GET /artifacts/{artifact_id}` => owned artifact content with Range support for media; no filesystem path input.
- `GET /catalog` => ComponentEntry[].
- `GET /settings` => sanitized settings and `configured` booleans. `PATCH /settings` => sanitized settings. Secrets are write-only and never in job/event/response/log. Model configuration supports only per-role CLI providers; voice/search/alignment outbound requests must be validated.

Voice settings accept `voice_provider:"none"|"byte_http"|"byte_ws"`, `voice_model` (maximum 200 chars; default `seed-tts-2.0-expressive`), voice/resource IDs, and write-only credentials. The WS endpoint is fixed to `wss://openspeech.bytedance.com/api/v3/tts/bidirection`; switching protocols without supplying an endpoint selects the corresponding official default. Public settings expose `voice_api_key_configured`, `voice_access_token_configured`, and aggregate `voice_configured`. WS requires API Key + voice ID + resource ID; legacy App ID/Access Token are HTTP-only. Blank credential fields are omitted by the frontend to preserve encrypted values.

WS uses official binary events 1/50, 100/150, 200/102, audio 352, subtitle 364, and matched completion 152. A durable `task_submitting` record precedes any text send. Failures before that point settle REJECTED; uncertainty after it settles UNKNOWN, including cancellation. Pending operations block both voice protocols within the revision. Only matched 152 and nonempty audio settle COMPLETED; decoding and text/timing coverage remain downstream gates. Credentials never enter ledger bodies. Request/connect/session IDs are diagnostic identifiers, not supplier idempotency guarantees.

WS DNS rejects non-public destinations. An all-`198.18.0.0/15` TUN resolution alone permits a bounded DoH lookup of the fixed vendor hostname via literal `1.1.1.1` with `cloudflare-dns.com` certificate/Host validation. The response is limited to 16 KiB, must answer that A question, and must contain only public addresses. Mixed/other private system resolutions still fail. This does not pass credentials or task content to DNS, follow redirects, change system DNS, or relax final vendor TLS validation.

### Per-role CLI model settings

`GET /models/{provider}?refresh=true` returns canonical `ModelCatalog`:
`{provider,status:"ready"|"unavailable"|"error",models:[{id,display_name,description,is_default,hidden}],message,fetched_at}`.
The endpoint requires the same local session as settings. Codex reads only the current user's `CODEX_HOME/models_cache.json` (default `~/.codex`), with a 4 MiB bound and 60-second in-process cache; refresh rereads the file. IDs map to cache `slug`, all entries including hidden models are retained, duplicate IDs retain their first entry. `fetched_at` is the cache's timestamp, not a new discovery timestamp. Cache results do not prove account access or freshness; no CLI subprocess/model request/auth-file read is used. Claude currently returns unavailable for automatic discovery and accepts custom names. Missing/invalid catalogs never restrict model settings. Frontend choices have separate UI tokens and save the original ID; directory loading/refresh does not mutate any role draft or enable a role.

`role_models` contains exactly `screenwriter`, `script_reviewer`, `voice`, `director`, `editing`, `review`. Each config is `{enabled:boolean,provider:"codex_cli"|"claude_code_cli",model:string,timeout_seconds:number}`; defaults are false, codex_cli, empty (CLI default), 300. Timeout range: 30–1800; model maximum: 200 characters. PATCH merges only supplied roles and supplied fields. Unknown roles/providers/fields are rejected. The old `llm_base_url`, `llm_model`, `llm_api_key` write interface is removed; existing encrypted records remain private and unused.

GET adds `cli_availability:{codex_cli:{available:boolean},claude_code_cli:{available:boolean}}` (executable discovery only), and `llm_configured` means at least one role is enabled. An enabled role with no executable blocks when invoked; it is not silently skipped. All six roles use the same durable model call budget and submission ledger. Provider/model changes cannot bypass a logical role/revision UNKNOWN barrier, including older HTTP submissions. Voice/editing models produce validated guidance artifacts; Byte/import alignment and Remotion remain the actual media executors. Human scripts and timelines retain priority; an enabled discussion may ask the writer model to revise an existing human draft.

Discussion settings are `script_discussion_enabled:boolean` (default false) and `script_discussion_max_rounds:integer` (default 2, range 1–5). These two settings freeze on first entry to the writer for each execution, before any draft/model result. Role/provider/model settings continue to apply to subsequent actual calls. One completed round is a writer submission followed by a critique. APPROVE leads to the deterministic source/material ScriptGate; REVISE loops to the writer while below the limit, otherwise interrupts for a versioned manual edit. Confirmation cannot waive an exhausted discussion. See [discussion workflow](videoagents-script-discussion.md).

CLI calls use argv, UTF-8 stdin, isolated temporary directories, bounded output, deadline/cancellation and process-tree cleanup. No model API-key form, no auth-file readback, no raw stderr exposure, no automatic provider fallback. Only a prelaunch failure establishes nonacceptance; any ambiguous postlaunch failure is UNKNOWN. Real CLI model calls require the account's login and access; subprocess protocol fixtures do not prove those external capabilities.

## Job models

The internal LangGraph `VideoState` now carries the complete Job projection plus public settings, research, media metadata, audio/alignment, guidance, render references, human receipts, operation summaries, metrics and JSON-only `extras`. This does not change the HTTP Job schema. Built-in nodes validate/persist writable context inputs before stage updates; SQL-ahead recovery, cancellation, version and approval bindings remain authoritative. Context-supplied assets must be backed by current-job file receipts. See [context fields and custom nodes](videoagents-context.md).

Brief: `{topic:string, script_text:string, audience:string, platform:string, usage:"personal"|"commercial"|"unspecified", target_seconds:number, width:number, height:number, fps:number, source_urls:string[]}`. Defaults: topic/script_text empty, audience "普通观众", platform "通用竖屏", usage "unspecified", target_seconds 60, width 1080, height 1920, fps 30, source_urls []. Topic or script_text required at creation.

Job: `{job_id:string, revision:number, status:string, stage:string, message:string, progress:number|null, created_at:string, updated_at:string, brief:Brief, script:Script|null, script_discussion:ScriptDiscussion|null, timeline:Timeline|null, assets:Asset[], artifacts:Artifact[], review:Review|null, pending_input:object|null, latest_event_id:number}`.

Statuses: `DRAFT`, `QUEUED`, `RUNNING`, `NEEDS_INPUT`, `NEEDS_HUMAN`, `READY_FOR_PUBLISH`, `REJECTED`, `FAILED`, `CANCELLED`. Stages: `idle`, `script`, `voice`, `director`, `render`, `review`, `complete`.

Optional stage approval: `HumanReviewNode` is registered as `human_review` without an incoming edge by default. Use `VideoProductionGraph.add_human_review()` and replace a stage's success edge to enable it. Pending input uses `{kind:"stage_review",stage,title,node_name,thread_id,revision,pending_token,dependency_fingerprint,policy_fingerprint,confirmation_requirements:string[],min_note_length:number}`; `issues` may appear after invalid notes. `NEEDS_HUMAN` applies even without a final video or `Review`. The existing resume API accepts `confirm` / `revise` / `cancel`; worker includes the bound token in the interrupt answer. Confirm continues to the configured next node; revise stops in DRAFT for versioned manual edits; cancel terminates. Confirmation leading to END settles as DRAFT. Stage decisions are immutable `stage_review` artifacts and do not set `Review.human_confirmed` or `READY_FOR_PUBLISH`. Sequential review points are supported; simultaneous parallel pending inputs are not. See [orchestration examples](videoagents-human-review.md).

Script: `{title:string, segments:[{segment_id:string,narration:string,screen_text:string,source_refs:string[],asset_ids:string[]}], origin:"user"|"model", revision:number}`.

ScriptDiscussion: `{run_id:string,revision:number,enabled:boolean,max_rounds:number,status:"DISABLED"|"DISCUSSING"|"APPROVED"|"EXHAUSTED",rounds:[{round:number,script:Script,response:string,critique:ScriptCritique|null}]}`. The current unreviewed draft has a null critique and does not count as a completed review. ScriptCritique: `{decision:"APPROVE"|"REVISE",summary:string,strengths:string[],issues:[{segment_id:string,category:"fact"|"logic"|"hook"|"clarity"|"visual"|"rights",concern:string,suggestion:string}]}`. Blank segment ID denotes a whole-script issue; other IDs must exist. REVISE requires issues; APPROVE requires no unresolved issues. ScriptRewrite is `{script:Script,response:string}` and its source/material references must pass deterministic validation. Each turn saves immutable JSON artifacts and the current script/discussion together to the Job; SQL already committed turns take priority on checkpoint replay. Versioned manual edits/imports invalidate the discussion.

Asset: `{asset_id:string, name:string, role:string, mime_type:string, size_bytes:number, sha256:string, source_url:string, license_note:string, artifact_id:string, url:string,timeline_src:string}`. Artifact: `{artifact_id:string,kind:string,name:string,mime_type:string,size_bytes:number,sha256:string,url:string,revision:number}`. All URLs for browser playback/download use `/api/artifacts/<id>`; raw absolute paths are internal only. `timeline_src` is a validated job-scoped relative source selectable in the editor.

ComponentEntry: `{component_id:string,name:string,description:string,use_case:string,library:string,kind:"adapter"|"preset",orientation:string,production_ready:boolean,min_frames:number,allowed_usages:("personal"|"commercial"|"unspecified")[],license_note:string,preview_url:string|null}`. `GET /catalog` returns the canonical 160-entry production manifest: 8 parameterized adapters plus 152 executable community presets. Clients filter by `Brief.usage`; the 108 Talkcraft presets are noncommercial and therefore excluded from commercial selection.

Review: `{status:string, findings:[{finding_id:string,severity:"error"|"warning"|"info",category:string,message:string,owner:string,blocking:boolean,start_frame:number|null,end_frame:number|null}], media_sha256:string|null, dependency_fingerprint:string, coverage:string[], human_confirmed:boolean}`. Missing credentials/capabilities result in explicit pending input, never fake outputs.

## Timeline shared between Python / React / Remotion

Timeline: `{schema_version:"1",job_id:string,revision:number,width:number,height:number,fps:number,duration_in_frames:number,audio_src:string|null,shots:Shot[],captions:Caption[]}`.

Shot: `{shot_id:string,start_frame:number,end_frame:number,component_id:string,title:string,body:string,asset_src:string|null,source_label:string,accent_color:string,props:object}`. Intervals left-closed/right-open; shots cover [0,duration_in_frames) contiguously. `component_id` must be one of the 160 IDs generated in `videoagents/component-manifest.json` and must be allowed by the current `Brief.usage`. The eight adapters (`title`, `keyword`, `evidence`, `image_focus`, `comparison`, `data`, `steps`, `conclusion`) accept only their typed content props; the 152 presets require `props={}` and `asset_src=null`. No component accepts arbitrary code, import paths, CSS, URLs, functions or unsupported factual values.

Caption: `{text:string,start_ms:number,end_ms:number}`. Timestamps come from the audio provider or verified imported alignment. No automatic equal-character estimates presented as real alignment.

Internal media sources passed to Remotion are job-controlled `videoagents/<job_id>/...` relative asset paths under `public/`; absolute paths, network URLs and traversal are rejected. The backend MUST copy/snapshot approved audio and images into public paths before rendering, not feed browser artifact API URLs requiring an API session into Remotion. Titles are at most 100 characters, bodies 240, source labels 160 and individual captions 72. Each parameterized adapter has a strict props allowlist; presets expose no custom props and render the registered horizontal or native vertical implementation according to timeline orientation.

`node scripts/render-timeline.mjs --timeline <absolute-json> --output <absolute-mp4> --mode preview|final [--cover <absolute-png>]`: validate input, reuse frozen inputProps for selectComposition/renderMedia, emit JSON lines `{event:"progress",progress:number}` and final `{event:"complete",output:string,cover:string|null}`. Nonzero exit on validation/render failure. Renderer accepts only local input and controlled relative media paths. Composition ID `VideoFromTimeline`. Preview can scale output; timeline coordinates remain canonical.

## Operating invariants

- API commands persisted before returning; worker consumes separately. Refresh or disconnected SSE never restarts paid work.
- Paid submission with unknown acceptance is UNKNOWN; do not retry blindly.
- Revise/replace audio or image invalidates affected artifacts and old review. Pending review binds revision and full dependency fingerprint.
- Real audio, source screenshots and voice cloning require available providers. App must support manual script/source/asset/audio+alignment input to complete a real workflow without fabricating integrations.
- Test fixtures can use synthesized test tones and labelled test scripts, never mark output as production ready via fixture bypass.
- Runtime files live in `.runtime/videoagents/jobs/<job_id>/`; controlled renderer copies live in `public/videoagents/<job_id>/`. Browser artifact URLs are authenticated and support Range requests.
- Secret configuration is write-only, with Windows DPAPI protection. Provider rejection recovery and UNKNOWN recovery have separate rules; transient source receipt IDs must not change a paid operation's semantic identity.
- No platform posting, no secret in Git; preserve all preexisting user files.
