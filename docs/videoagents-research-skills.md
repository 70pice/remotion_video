# VideoAgents research skill inventory

Updated: 2026-10-04

This file records the machine-level research skills and CLIs that the Materials
node can ask a local Codex CLI session to use. It is an operational inventory,
not a guarantee that every platform is logged in or reachable.

## Installed skills

| Skill | SKILL.md | Purpose | Status |
| --- | --- | --- | --- |
| agent-reach | `C:\Users\70pic\.codex\skills\agent-reach\SKILL.md` | Primary internet and social-media research router. Covers web, Exa, GitHub, YouTube, Bilibili, V2EX, RSS, X/Twitter, Reddit, Xiaohongshu, Facebook, Instagram, LinkedIn, Xueqiu, Xiaoyuzhou and Boss through multiple backends. | Installed as a junction to `C:\Users\70pic\.agents\skills\agent-reach`; use this first for materials research. |
| playwright | `C:\Users\70pic\.codex\skills\playwright\SKILL.md` | Browser automation for pages that need navigation, screenshots, DOM snapshots, or visual extraction. | Installed from `openai/skills` curated skills. `npx` is available. |
| screenshot | `C:\Users\70pic\.codex\skills\screenshot\SKILL.md` | OS-level screenshot fallback when browser or platform tools cannot capture a page/window. | Installed from `openai/skills` curated skills. |
| transcribe | `C:\Users\70pic\.codex\skills\transcribe\SKILL.md` | Audio/video transcription with OpenAI models when a video has no usable subtitles. | Installed from `openai/skills` curated skills. Requires `OPENAI_API_KEY` for live calls. |

The original Agent Reach skill also remains at
`C:\Users\70pic\.agents\skills\agent-reach\SKILL.md`.

## Source provenance

| Component | Install source | Ref recorded by installer | Local integrity record |
| --- | --- | --- | --- |
| agent-reach skill | `https://github.com/Panniantong/Agent-Reach` via `agent-reach skill --install`; `.codex` path is a junction to the existing `.agents` skill | No fixed ref recorded for the skill directory. Current `main` observed on 2026-10-04 was `a19a171fa980a0785849596492e0af4db800c82f`, but the installed skill should be treated as a local snapshot. | `SKILL.md` SHA256 `a9e985954a6436a35426203f062a3089dbba2aa6819775dd33b0bc9f0980fa7a` |
| agent-reach CLI | `uv tool install https://github.com/Panniantong/agent-reach/archive/main.zip --upgrade` | `direct_url.json` records only `https://github.com/Panniantong/agent-reach/archive/main.zip`; no commit/ref lock was recorded. Current `main` observed on 2026-10-04 was `a19a171fa980a0785849596492e0af4db800c82f`, but that is not proof of the exact installed archive. | `direct_url.json` SHA256 `d8afb2fb0a217bddb0276c35b709d5b42c511546bd610f04319aedc0aa9266ac`; package version `1.5.0` |
| playwright skill | `https://github.com/openai/skills/tree/main/skills/.curated/playwright` through `skill-installer` | Installed without an explicit `--ref`, so this is a 2026-10-04 `main` snapshot. Current `openai/skills` `main` observed after install was `49f948faa9258a0c61caceaf225e179651397431`; local SHA is the durable record. | `SKILL.md` SHA256 `0ffaabcc8e0990627c4725f18bf1c7955534a796c1c199e872909de2013ce6a8` |
| screenshot skill | `https://github.com/openai/skills/tree/main/skills/.curated/screenshot` through `skill-installer` | Installed without an explicit `--ref`; treat as a 2026-10-04 `main` snapshot. | `SKILL.md` SHA256 `081935a6a163277537d46365f49d6b4a3cb40b4748347e7e88759c5927fa8cf5` |
| transcribe skill | `https://github.com/openai/skills/tree/main/skills/.curated/transcribe` through `skill-installer` | Installed without an explicit `--ref`; treat as a 2026-10-04 `main` snapshot. | `SKILL.md` SHA256 `f530021da9f377362ee4214e0bc689cbb5404640d2eb88ee272d51d61f530a09` |

## Installed or detected CLIs

| Tool | Source / install method | Check result | Notes |
| --- | --- | --- | --- |
| `agent-reach` | `uv tool install https://github.com/Panniantong/agent-reach/archive/main.zip --upgrade` | `agent-reach --help` works with `C:\Users\70pic\.local\bin` prepended to PATH. Version from upstream pyproject: `1.5.0`. | `C:\Users\70pic\.local\bin` is not in the persistent PATH yet. Materials runner should prepend it in the child process environment. |
| `yt-dlp` | `uv tool install "yt-dlp[default]" --upgrade` | `yt-dlp --version` -> `2026.08.19`; `agent-reach doctor --json` marks YouTube `ok` with active backend `yt-dlp`. | Use for YouTube search, metadata, subtitles, thumbnails and storyboard URLs. |
| `bili` | `uv tool install bilibili-cli --upgrade` | `agent-reach doctor --json` marks Bilibili `ok` with active backend `bili-cli`; `bili search "Muse是什么" --type video -n 2` returned results. | Set `PYTHONUTF8=1` on Windows to avoid GBK encoding errors in help output. |
| `opencli` | Already installed globally through Node | `opencli doctor` reports daemon running and Chrome extension connected. | OpenCLI can serve Xiaohongshu, Reddit, X/Twitter, Facebook, Instagram, and Bilibili subtitles when the browser login state is valid. Doctor does not execute logged-in platform calls. |
| `mcporter` | Already installed globally through Node | `mcporter list --json` reports `exa` status `ok` and exposes `web_search_exa` / `web_fetch_exa`. | `node_repl` was offline during the check; that is unrelated to materials search. |
| `gh` | Already installed | `agent-reach doctor --json` sees the CLI, but intentionally does not run `gh auth status`. | Use for public GitHub search and repository lookup. Avoid write operations. |
| `npx` | Already installed with Node | `npx --version` -> `11.16.0`. | Required by the Playwright skill wrapper. |
| Playwright CLI | `npx --yes --package @playwright/cli playwright-cli` | `playwright-cli --version` -> `0.1.22`; Windows smoke test opened `https://example.com`, captured a screenshot, and closed the session. | The installed skill wrapper is `scripts/playwright_cli.sh`, but this Windows host has no `bash`; use direct `npx` invocation on Windows. Playwright browser cache exists under `C:\Users\70pic\AppData\Local\ms-playwright`. |

## Current platform status

Status comes from `agent-reach doctor --json` plus targeted read-only smoke tests.

| Platform / channel | Current status | Backend to use first | What is missing |
| --- | --- | --- | --- |
| Web pages | OK | Jina Reader (`https://r.jina.ai/URL`) | None for public pages. |
| Exa semantic search | OK | `mcporter call 'exa.web_search_exa(query: "...", numResults: 5)'` | None observed; keep calls read-only. |
| YouTube | OK | `yt-dlp` | None for public metadata/search/subtitles. |
| Bilibili | OK | `bili-cli`; OpenCLI for subtitles | Browser login may be needed for some subtitle or personalized content. |
| V2EX | OK | Public V2EX API | None for public topics and replies. |
| RSS / Atom | OK | `feedparser` through Agent Reach guidance | None for public feeds. |
| GitHub | Warn | `gh search ...` | Doctor did not run auth verification. Public search can work without extra authorization; authenticated rate limits depend on the user's `gh` state. |
| X / Twitter | Warn | OpenCLI first; `twitter-cli` if cookies are explicitly configured | Requires valid browser session or user-provided cookies. |
| Reddit | Search/body verified | OpenCLI first | 2026-10-04: two Meta Muse search results, one complete post and two comments through the existing Chrome session. |
| Zhihu | Body verified; search failed | OpenCLI | A specified article exported successfully; the search endpoint returned AUTH_REQUIRED in the same Chrome session. |
| Xiaohongshu | Warn | OpenCLI first | Requires Chrome login state or explicitly provided cookies for non-OpenCLI backends. |
| Facebook | Warn | OpenCLI | Requires Chrome login state. |
| Instagram | Warn | OpenCLI | Requires Chrome login state. Instagram search is user/profile oriented, not full post keyword search. |
| LinkedIn | Warn | Jina Reader fallback; LinkedIn MCP if configured later | No LinkedIn MCP configured. Full profile/jobs search needs login. |
| Xueqiu | Warn | Xueqiu API after explicit cookie configuration | Doctor received HTTP 400 without cookies. |
| Xiaoyuzhou podcast | Off | Agent Reach Xiaoyuzhou tool or `transcribe` fallback | Xiaoyuzhou helper and Groq key are not configured. |
| Boss Zhipin | Off | Agent Reach Boss channel | Requires a dedicated Chrome profile, local CDP, and user login. Not needed for short-video materials unless job data is the topic. |

## Recommended MaterialsNode prompt contract

When the role provider is `codex_cli`, the Materials node should instruct the
CLI session to:

1. Read `C:\Users\70pic\.codex\skills\agent-reach\SKILL.md` first.
2. Use Agent Reach routing for platform selection and run
   `agent-reach doctor --json` at the beginning of the task.
3. Prepend `C:\Users\70pic\.local\bin` to PATH for the child process so that
   `agent-reach`, `yt-dlp`, and `bili` are available.
4. Prefer zero-login channels first: Exa, Jina Reader, YouTube, Bilibili, V2EX,
   RSS and public GitHub.
5. Use OpenCLI for social platforms only when the current browser login state is
   enough. Do not ask for passwords, do not post, comment, like, follow, send
   messages, buy services, or publish content.
6. If screenshots or page interaction are required, read
   `C:\Users\70pic\.codex\skills\playwright\SKILL.md`; on Windows call
   `npx --yes --package @playwright/cli playwright-cli ...` directly because
   the skill's Bash wrapper is not executable on this host. Use
   `C:\Users\70pic\.codex\skills\screenshot\SKILL.md` only as the fallback.
7. If a relevant public video has no subtitle, read
   `C:\Users\70pic\.codex\skills\transcribe\SKILL.md`; only transcribe when an
   API key is already present in the local environment.
8. Return a final JSON manifest with only durable outputs: source URLs, quoted or
   summarized evidence, local asset file paths, capture method, platform,
   backend, timestamp, confidence, and limitations. Do not return raw tool
   traces, cookies, environment variables, or command logs.

## Smoke-test evidence

- `agent-reach doctor --json` marked `youtube`, `bilibili`, `v2ex`, `rss`, and
  `web` as `ok`.
- `mcporter list --json` marked the `exa` MCP server as `ok` and listed
  `web_search_exa` and `web_fetch_exa`.
- `opencli doctor` reported daemon `v1.8.6` running and the Chrome extension
  connected. It also reported an available OpenCLI update to `v1.8.8`; no update
  was applied.
- `bili search "Muse是什么" --type video -n 2` returned two Bilibili results:
  `BV195hH6cE3M` and `BV1H5af6SEDu`.
- `yt-dlp --dump-json "ytsearch1:Muse AI video editor" --skip-download` parsed a
  public YouTube result and returned metadata for video `B6CVKNvc3y4`.
- Jina Reader returned markdown for `https://example.com`.
- Playwright CLI Windows smoke test succeeded with
  `npx --yes --package @playwright/cli playwright-cli --session videoagents-smoke open https://example.com`,
  then `screenshot`, then `close`. This produced a local PNG screenshot.
- The application MaterialsNode was also exercised with a real `gpt-6.1-sol`
  research session against the Muse official website. It saved one UTF-8 source
  and one real 750x1260 image, validated six registered artifact hashes, and
  routed to `screenwriter`. Replaying with model invocation disabled reused the
  frozen research and created no new operations. This did not run TTS or render
  a video. See [Materials node verification](videoagents-materials.md).
- A subsequent real Codex research transport probe read Meta's help-center body
  through Jina Reader, searched Exa and Bilibili, read Bilibili video details, and
  obtained YouTube metadata. The YouTube subtitle download returned HTTP 429.
  Platform-specific tests also obtained Reddit and Zhihu bodies. See
  [tool diagnostics](videoagents-tool-diagnostics.md) for per-capability results.

## Known operational notes

- The user-level executable directory `C:\Users\70pic\.local\bin` is not in the
  persistent PATH. The application should prepend it for local CLI subprocesses
  instead of requiring a global shell change.
- Do not print or store API keys, cookies, session tokens, browser profiles, or
  raw environment variables in job artifacts.
- Treat `warn` platforms as opportunistic: try them only after `doctor` shows an
  appropriate backend and the task benefits from that platform. Always record
  login/API limitations in the research manifest.
