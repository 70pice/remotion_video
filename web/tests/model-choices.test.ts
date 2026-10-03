import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  catalogModelChoice,
  customModelChoice,
  defaultModelChoice,
  formatModelCacheTime,
  modelFromChoice,
  selectedModelChoice,
} from "../src/api/modelChoices";
import { buildRoleModelsPatch, readRoleModels } from "../src/api/roleSettings";
import type { ModelCatalog } from "../src/api/types";
import { SettingsForm } from "../src/pages/SettingsPage";

const catalog: ModelCatalog = {
  provider: "codex_cli",
  status: "ready",
  models: [
    {
      id: "future/model:v2",
      display_name: "目录显示名称",
      description: "由 CLI 动态返回的说明",
      is_default: true,
      hidden: false,
    },
    {
      id: "custom",
      display_name: "另一个隐藏模型",
      description: "隐藏项也应可以选择",
      is_default: false,
      hidden: true,
    },
  ],
  message: "",
  fetched_at: "2026-10-03T00:00:00Z",
};

describe("Codex model choices", () => {
  it("keeps CLI default independent from the directory's default model", () => {
    expect(selectedModelChoice("", catalog)).toBe(defaultModelChoice);
    expect(modelFromChoice(defaultModelChoice, "future/model:v2")).toBe("");
  });

  it("preserves opaque model IDs even when they collide with UI choice names", () => {
    for (const id of [
      "custom",
      "default",
      "catalog:custom",
      "future/model:v2",
    ]) {
      expect(modelFromChoice(catalogModelChoice(id), "old-model")).toBe(id);
    }
    const saved = readRoleModels({});
    const draft = {
      ...saved,
      voice: {
        ...saved.voice,
        model: modelFromChoice(catalogModelChoice("future/model:v2"), ""),
      },
    };
    expect(buildRoleModelsPatch(draft, saved)).toEqual({
      voice: { model: "future/model:v2" },
    });
  });

  it("supports entering custom models and retains saved models absent from the directory", () => {
    expect(selectedModelChoice("", catalog, true)).toBe(customModelChoice);
    expect(selectedModelChoice("outside-catalog", catalog)).toBe(
      customModelChoice,
    );
    expect(modelFromChoice(customModelChoice, "outside-catalog")).toBe(
      "outside-catalog",
    );
    expect(selectedModelChoice("future/model:v2", catalog)).toBe(
      catalogModelChoice("future/model:v2"),
    );
    expect(selectedModelChoice("future/model:v2", undefined)).toBe(
      customModelChoice,
    );
  });
});

type FormProps = Parameters<typeof SettingsForm>[0];
function renderForm(overrides: Partial<FormProps> = {}): string {
  const settings = { role_models: readRoleModels({}) };
  return renderToStaticMarkup(
    createElement(SettingsForm, {
      saved: settings,
      values: settings,
      busy: false,
      modelCatalog: catalog,
      onChange: () => undefined,
      onSubmit: () => undefined,
      onRefreshModels: () => undefined,
      ...overrides,
    }),
  );
}

describe("dynamic directory form", () => {
  it("renders the entire CLI directory including hidden IDs in each Codex selector", () => {
    const markup = renderForm();
    expect(markup.match(/value="catalog:future\/model:v2"/g)).toHaveLength(5);
    expect(markup.match(/value="catalog:custom"/g)).toHaveLength(5);
    expect(markup).toContain("目录显示名称 · future/model:v2");
    expect(markup).toContain("（目录隐藏项）");
    expect(markup).toContain("CLI 默认模型");
    expect(markup).toContain("自定义模型");
    expect(markup).toContain("从本机 Codex 模型缓存读取");
    expect(markup).toContain("可选列表不代表当前账号权限");
    expect(markup).toContain("重读模型列表");
    expect(markup).toContain("重读列表只读取该缓存");
    expect(markup).toContain("已读取 2 个模型，含隐藏项");
    expect(markup).toContain('<time dateTime="2026-10-03T00:00:00Z">');
    expect(markup).not.toContain(">2026-10-03T00:00:00Z</time>");
    expect(markup).toContain("缓存生成时间（本地）");
  });

  it("uses a local Chinese cache timestamp and avoids repeating a ready catalog message", () => {
    const timestamp = "2026-10-03T12:34:56.123456789Z";
    const markup = renderForm({
      modelCatalog: {
        ...catalog,
        message: "重复的后端目录来源说明",
        fetched_at: timestamp,
      },
    });
    expect(markup).not.toContain("重复的后端目录来源说明");
    expect(markup).toContain(`dateTime="${timestamp}"`);
    const display = formatModelCacheTime(timestamp);
    expect(display).toContain("年");
    expect(display).toContain("月");
    expect(display).not.toContain("123456789");
    expect(display).not.toContain("T");
    expect(markup).toContain(`>${display}</time>`);
    expect(formatModelCacheTime("invalid-timestamp")).toBe("未知");
  });

  it("keeps unsaved model values when a directory refresh removes or fails to return a model", () => {
    const saved = { role_models: readRoleModels({}) };
    const roles = readRoleModels(saved);
    roles.screenwriter.model = "future/model:v2";
    roles.director.model = "outside-catalog";
    const values = { role_models: roles };
    const before = JSON.stringify(values);
    const refreshed = { ...catalog, models: [] };
    const markup = renderForm({ saved, values, modelCatalog: refreshed });
    expect(markup).toContain('aria-label="编剧模型名称"');
    expect(markup).toContain('value="future/model:v2"');
    expect(markup).toContain('value="outside-catalog"');

    const pending = renderForm({ saved, values, catalogLoading: true });
    expect(pending).toContain("仍可编辑角色配置");
    expect(pending).not.toContain(
      '<fieldset class="editor-fieldset" disabled="">',
    );
    const failed = renderForm({ saved, values, catalogError: "刷新目录失败" });
    expect(failed).toContain("当前保留上次读取的列表");
    expect(failed).toContain('value="catalog:future/model:v2" selected=""');
    expect(JSON.stringify(values)).toBe(before);
    expect(buildRoleModelsPatch(roles, readRoleModels(saved))).toEqual({
      screenwriter: { model: "future/model:v2" },
      director: { model: "outside-catalog" },
    });
  });

  it("keeps Claude models as text input and retains their ID when the provider changes", () => {
    const roles = readRoleModels({});
    roles.editing = {
      ...roles.editing,
      provider: "claude_code_cli",
      model: "claude/custom-id",
    };
    const values = { role_models: roles };
    const markup = renderForm({ values });
    expect(markup).toContain('aria-label="剪辑模型名称"');
    expect(markup).toContain('value="claude/custom-id"');
    expect(markup).not.toContain('aria-label="剪辑模型选择"');

    const switched = {
      ...roles,
      editing: { ...roles.editing, provider: "codex_cli" as const },
    };
    const switchedMarkup = renderForm({ values: { role_models: switched } });
    expect(switchedMarkup).toContain('aria-label="剪辑模型选择"');
    expect(switchedMarkup).toContain('aria-label="剪辑模型名称"');
    expect(switchedMarkup).toContain('value="claude/custom-id"');
  });
});
