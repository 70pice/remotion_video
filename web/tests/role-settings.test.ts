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
  it("starts all five roles disabled and keeps their defaults independent", () => {
    const roles = readRoleModels({});
    expect(Object.keys(roles)).toEqual([
      "screenwriter",
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

  it("submits only the changed fields independently for all five edited roles", () => {
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
        screenwriter: {
          enabled: true,
          model: "screenwriter-model",
          timeout_seconds: 30,
        },
        voice: {
          enabled: true,
          provider: "claude_code_cli",
          timeout_seconds: 230,
        },
        director: {
          enabled: true,
          model: "director-model",
          timeout_seconds: 430,
        },
        editing: {
          enabled: true,
          provider: "claude_code_cli",
          model: "editing-model",
          timeout_seconds: 630,
        },
        review: { enabled: true, model: "review-model", timeout_seconds: 830 },
      },
    });
    expect(payload.role_models?.voice?.model).toBeUndefined();
    expect(payload.role_models?.editing?.provider).toBe("claude_code_cli");
  });

  it("saves disabling one role without replacing the other four roles", () => {
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
      aligner_api_key: "",
      capture_enabled: true,
    };
    expect(createSettingsPayload(values, saved)).toEqual({
      voice_provider: "byte_http",
      voice_api_key: "new-voice-key",
      search_provider: "tavily",
      capture_enabled: true,
    });
  });
});

function renderForm(busy: boolean): string {
  const settings: Settings = {
    role_models: readRoleModels({}),
    cli_availability: {
      codex_cli: { available: false },
      claude_code_cli: { available: true },
    },
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
  it("renders five accessible role controls and clearly identifies an unavailable CLI", () => {
    const markup = renderForm(false);
    for (const { label } of modelRoles) {
      expect(markup).toContain(`aria-label="启用${label}模型"`);
      expect(markup).toContain(`aria-label="${label}模型提供方"`);
      expect(markup).toContain(`aria-label="${label}模型选择"`);
      expect(markup).toContain(`aria-label="${label}模型超时秒数"`);
    }
    expect(markup.match(/value="claude_code_cli"/g)).toHaveLength(5);
    expect(markup).toContain("未检测到 Codex CLI，当前不可用");
    expect(markup).toContain("检测只确认是否安装");
    expect(markup).toContain(
      "仅影响后续实际调用；已有文案、分镜和产物不会自动重做。",
    );
    expect(markup).toContain("真实声音仍由字节配音接口生成");
    expect(markup).toContain("视频仍由 Remotion 实际渲染");
    expect(markup).not.toContain("编剧与导演模型");
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
