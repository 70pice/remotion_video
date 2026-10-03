import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  buildRoleModelsPatch,
  modelRoles,
  readRoleModels,
} from "../src/api/roleSettings";
import type { RoleModels, Settings } from "../src/api/types";
import { createSettingsPayload, SettingsForm } from "../src/pages/SettingsPage";

describe("independent role model settings", () => {
  it("starts all seven roles disabled and keeps their defaults independent", () => {
    const roles = readRoleModels({});
    expect(Object.keys(roles)).toEqual([
      "materials",
      "screenwriter",
      "script_reviewer",
      "voice",
      "director",
      "editing",
      "review",
    ]);
    for (const { id } of modelRoles) {
      expect(roles[id]).toEqual({
        enabled: false,
        provider: "codex_cli",
        model: "",
        timeout_seconds: 300,
      });
    }
    roles.voice.model = "voice-model";
    expect(roles.director.model).toBe("");
  });

  it("submits only the changed fields independently for all seven edited roles", () => {
    const saved = readRoleModels({});
    const draft = readRoleModels({});
    modelRoles.forEach(({ id }, index) => {
      draft[id] = {
        enabled: true,
        provider: index % 2 ? "claude_code_cli" : "codex_cli",
        model: id === "voice" ? "" : `${id}-model`,
        timeout_seconds: 30 + index * 200,
      };
    });

    const payload = createSettingsPayload(
      { role_models: draft },
      { role_models: saved },
    );
    expect(payload).toEqual({
      role_models: {
        materials: {
          enabled: true,
          model: "materials-model",
          timeout_seconds: 30,
        },
        screenwriter: {
          enabled: true,
          provider: "claude_code_cli",
          model: "screenwriter-model",
          timeout_seconds: 230,
        },
        script_reviewer: {
          enabled: true,
          model: "script_reviewer-model",
          timeout_seconds: 430,
        },
        voice: {
          enabled: true,
          provider: "claude_code_cli",
          timeout_seconds: 630,
        },
        director: {
          enabled: true,
          model: "director-model",
          timeout_seconds: 830,
        },
        editing: {
          enabled: true,
          model: "editing-model",
          provider: "claude_code_cli",
          timeout_seconds: 1030,
        },
        review: {
          enabled: true,
          model: "review-model",
          timeout_seconds: 1230,
        },
      },
    });
    expect(payload.role_models?.voice?.model).toBeUndefined();
    expect(payload.role_models?.editing?.provider).toBe("claude_code_cli");
  });

  it("saves disabling one role without replacing the other five roles", () => {
    const saved = readRoleModels({});
    saved.director = {
      enabled: true,
      provider: "claude_code_cli",
      model: "director-model",
      timeout_seconds: 1800,
    };
    const draft: RoleModels = {
      ...saved,
      director: { ...saved.director, enabled: false },
    };
    expect(buildRoleModelsPatch(draft, saved)).toEqual({
      director: { enabled: false },
    });
    expect(buildRoleModelsPatch(saved, saved)).toEqual({});
  });

  it("does not overwrite newer role fields and can intentionally restore the CLI default model", () => {
    const saved = readRoleModels({});
    saved.review = { ...saved.review, model: "previous-model" };
    const draft = {
      ...saved,
      review: { ...saved.review, model: "" },
    };
    const patch = buildRoleModelsPatch(draft, saved);
    expect(patch).toEqual({ review: { model: "" } });

    const newerServerConfig = {
      ...saved.review,
      enabled: true,
      provider: "claude_code_cli" as const,
      timeout_seconds: 900,
    };
    expect({ ...newerServerConfig, ...patch.review }).toEqual({
      enabled: true,
      provider: "claude_code_cli",
      model: "",
      timeout_seconds: 900,
    });
  });

  it("preserves blank service secrets and excludes obsolete global HTTP model fields", () => {
    const saved: Settings = { role_models: readRoleModels({}) };
    const values: Settings = {
      ...saved,
      llm_base_url: "https://old-model.example/v1",
      llm_model: "obsolete-model",
      llm_api_key: "obsolete-key",
      voice_provider: "byte_http",
      voice_api_key: "new-voice-key",
      voice_access_token: "",
      search_provider: "tavily",
      search_api_key: "",
      google_search_engine_id: "unit-cx",
      research_platforms: ["web", "youtube"],
      research_download_images: false,
      aligner_api_key: "",
      capture_enabled: true,
    };
    expect(createSettingsPayload(values, saved)).toEqual({
      voice_provider: "byte_http",
      voice_api_key: "new-voice-key",
      voice_style: "",
      voice_speech_rate: 0,
      search_provider: "tavily",
      google_search_engine_id: "unit-cx",
      research_platforms: ["web", "youtube"],
      research_download_images: false,
      capture_enabled: true,
    });
  });


  it("sends WebSocket expressive voice performance controls and hides them for HTTP", () => {
    const saved: Settings = { role_models: readRoleModels({}) };
    const values: Settings = {
      ...saved,
      voice_provider: "byte_ws",
      voice_model: "seed-tts-2.0-expressive",
      voice_style: "像面对观众讲解：开头好奇、重点加重、句间自然停顿，避免播报腔",
      voice_speech_rate: 24.6,
    };

    expect(createSettingsPayload(values, saved)).toMatchObject({
      voice_provider: "byte_ws",
      voice_model: "seed-tts-2.0-expressive",
      voice_style: "像面对观众讲解：开头好奇、重点加重、句间自然停顿，避免播报腔",
      voice_speech_rate: 25,
    });
    expect(
      createSettingsPayload(
        { ...values, voice_provider: "byte_http", voice_speech_rate: 20 },
        saved,
      ),
    ).toMatchObject({ voice_style: "", voice_speech_rate: 0 });
  });

  it("patches script discussion settings only when they changed", () => {
    const saved: Settings = {
      role_models: readRoleModels({}),
      script_discussion_enabled: false,
      script_discussion_max_rounds: 2,
    };
    expect(createSettingsPayload({ ...saved }, saved)).toEqual({});

    expect(
      createSettingsPayload(
        {
          ...saved,
          script_discussion_enabled: true,
          script_discussion_max_rounds: 6,
        },
        saved,
      ),
    ).toEqual({
      script_discussion_enabled: true,
      script_discussion_max_rounds: 5,
    });
  });
});

function renderForm(busy: boolean, overrides: Settings = {}): string {
  const settings: Settings = {
    role_models: readRoleModels({}),
    cli_availability: {
      codex_cli: { available: false },
      claude_code_cli: { available: true },
    },
    ...overrides,
  };
  return renderToStaticMarkup(
    createElement(SettingsForm, {
      saved: settings,
      values: settings,
      busy,
      onChange: () => undefined,
      onSubmit: () => undefined,
    }),
  );
}

describe("role settings form", () => {
  it("renders seven accessible role controls and clearly identifies an unavailable CLI", () => {
    const markup = renderForm(false);
    for (const { label } of modelRoles) {
      expect(markup).toContain(`aria-label="启用${label}模型"`);
      expect(markup).toContain(`aria-label="${label}模型提供方"`);
      expect(markup).toContain(`aria-label="${label}模型选择"`);
      expect(markup).toContain(`aria-label="${label}模型超时秒数"`);
    }
    expect(markup.match(/value="claude_code_cli"/g)).toHaveLength(7);
    expect(markup).toContain("未检测到 Codex CLI，当前不可用");
    expect(markup).toContain("检测只确认是否安装");
    expect(markup).toContain(
      "仅影响后续实际调用；已有文案、分镜和产物不会自动重做。",
    );
    expect(markup).toContain("真实声音仍由字节配音接口生成");
    expect(markup).toContain("视频仍由 Remotion 实际渲染");
    expect(markup).toContain("审查编剧稿件的事实、钩子、逻辑、画面与版权风险");
    expect(markup).toContain('aria-label="启用文案讨论"');
    expect(markup).toContain('aria-label="文案讨论最大审查轮数"');
    expect(markup).toContain("达到上限仍需修改时，流程会暂停等待处理");
    expect(markup).toContain("不会自动启用任何 CLI");
    expect(markup).not.toContain("编剧与导演模型");
  });


  it("renders WebSocket-only expressive style and speech-rate controls", () => {
    const wsMarkup = renderForm(false, { voice_provider: "byte_ws" });
    expect(wsMarkup).toContain('aria-label="讲述风格"');
    expect(wsMarkup).toContain('maxLength="2000"');
    expect(wsMarkup).toContain('placeholder="像面对观众讲解：开头好奇、重点加重、句间自然停顿，避免播报腔"');
    expect(wsMarkup).toContain('aria-label="语速调整"');
    expect(wsMarkup).toContain('min="-50"');
    expect(wsMarkup).toContain('max="100"');
    expect(wsMarkup).toContain('value="seed-tts-2.0-standard"');
    expect(wsMarkup).toContain('value="seed-tts-2.0-expressive"');
    expect(wsMarkup).toContain('seed-tts-2.0-standard');
    expect(wsMarkup).toContain('不支持情绪或表演指导');
    expect(wsMarkup).toContain('seed-tts-2.0-expressive');
    expect(wsMarkup).toContain('支持自然语言指导');

    const httpMarkup = renderForm(false, { voice_provider: "byte_http" });
    expect(httpMarkup).not.toContain('aria-label="讲述风格"');
    expect(httpMarkup).not.toContain('aria-label="语速调整"');
  });

  it("locks all role and service fields while the submitted snapshot is saving", () => {
    const markup = renderForm(true);
    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain('<fieldset class="editor-fieldset" disabled="">');
    const fieldset = markup.slice(
      markup.indexOf("<fieldset"),
      markup.indexOf("</fieldset>"),
    );
    for (const { label } of modelRoles) {
      expect(fieldset).toContain(`aria-label="启用${label}模型"`);
      expect(fieldset).toContain(`aria-label="${label}模型选择"`);
    }
    expect(fieldset).toContain("新鉴权 API Key");
    expect(fieldset).toContain(
      '<button class="button primary" disabled="">正在保存…</button>',
    );
    expect(renderForm(false)).not.toContain('disabled=""');
  });
});
