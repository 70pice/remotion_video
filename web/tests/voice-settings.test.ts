import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { readRoleModels } from "../src/api/roleSettings";
import type { Settings } from "../src/api/types";
import {
  createSettingsPayload,
  SettingsForm,
  voiceProviderPatch,
} from "../src/pages/SettingsPage";

const wsEndpoint = "wss://openspeech.bytedance.com/api/v3/tts/bidirection";
const httpEndpoint =
  "https://openspeech.bytedance.com/api/v3/tts/unidirectional";

function renderVoiceSettings(saved: Settings, values = saved): string {
  const markup = renderToStaticMarkup(
    createElement(SettingsForm, {
      saved,
      values,
      busy: false,
      onChange: () => undefined,
      onSubmit: () => undefined,
    }),
  );
  const start = markup.indexOf("<h2>你的声音</h2>");
  return markup.slice(start, markup.indexOf("</section>", start));
}

describe("ByteDance voice transport settings", () => {
  it("switches only the voice provider and its matching default endpoint", () => {
    const roles = readRoleModels({});
    roles.voice.model = "voice-guidance-model";
    const current = {
      role_models: roles,
      voice_id: "existing-cloned-voice",
      voice_resource_id: "account-specific-resource",
      voice_model: "custom-synthesis-model",
    };
    expect(voiceProviderPatch("byte_ws")).toEqual({
      voice_provider: "byte_ws",
      voice_endpoint: wsEndpoint,
    });
    expect(voiceProviderPatch("byte_http")).toEqual({
      voice_provider: "byte_http",
      voice_endpoint: httpEndpoint,
      voice_style: "",
      voice_speech_rate: 0,
    });
    expect(voiceProviderPatch("none")).toEqual({ voice_provider: "none" });
    const switched = { ...current, ...voiceProviderPatch("byte_ws") };
    expect(switched.role_models).toBe(roles);
    expect(switched.voice_id).toBe("existing-cloned-voice");
    expect(switched.voice_resource_id).toBe("account-specific-resource");
    expect(switched.voice_model).toBe("custom-synthesis-model");
  });

  it("submits WebSocket configuration and preserves hidden legacy credentials and a blank API key", () => {
    const values: Settings = {
      voice_provider: "byte_ws",
      voice_endpoint: wsEndpoint,
      voice_resource_id: "account-specific-resource",
      voice_id: "existing-cloned-voice",
      voice_api_key: "",
      voice_app_id: "legacy-app-id",
      voice_access_token: "unused-test-token",
    };
    expect(createSettingsPayload(values, {})).toEqual({
      voice_provider: "byte_ws",
      voice_endpoint: wsEndpoint,
      voice_resource_id: "account-specific-resource",
      voice_id: "existing-cloned-voice",
      voice_model: "seed-tts-2.0-standard",
      voice_style: "",
      voice_speech_rate: 0,
    });
    expect(values.voice_access_token).toBe("unused-test-token");
  });

  it("keeps the synthesis model separate from the CLI role's model in the request body", () => {
    const saved = { role_models: readRoleModels({}) };
    const roles = readRoleModels(saved);
    roles.voice.model = "cli-guidance-id";
    const payload = createSettingsPayload(
      {
        voice_provider: "byte_ws",
        voice_model: "custom-synthesis-id",
        voice_api_key: "new-test-key",
        role_models: roles,
      },
      saved,
    );
    expect(payload).toEqual({
      voice_provider: "byte_ws",
      voice_model: "custom-synthesis-id",
      voice_api_key: "new-test-key",
      voice_style: "",
      voice_speech_rate: 0,
      role_models: { voice: { model: "cli-guidance-id" } },
    });
  });

  it("shows wss input, synthesis defaults and only new authentication with its own configured flag", () => {
    const markup = renderVoiceSettings({
      ...voiceProviderPatch("byte_ws"),
      voice_resource_id: "account-specific-resource",
      voice_id: "existing-cloned-voice",
      voice_api_key_configured: true,
      voice_access_token_configured: false,
      voice_configured: false,
    });
    expect(markup).toContain('value="byte_ws" selected=""');
    expect(markup).toContain("字节 WebSocket 双向流式");
    expect(markup).toContain('aria-label="配音接口地址" type="url"');
    expect(markup).toContain(`value="${wsEndpoint}"`);
    expect(markup).toContain('aria-label="语音合成模型"');
    expect(markup).toContain('value="seed-tts-2.0-expressive"');
    expect(markup).toContain('value="seed-tts-2.0-standard"');
    expect(markup).toContain('aria-label="情感风格预设"');
    expect(markup).toContain('aria-label="情感与讲述风格"');
    expect(markup).toContain('aria-label="语速（倍速）"');
    expect(markup).toContain('语速范围 0.5～2.0 倍');
    expect(markup).toContain('standard 不支持情感指导');
    expect(markup).not.toContain('保存时会转换成后端');
    expect(markup).toContain("与配音角色的 CLI 指导模型独立");
    expect(markup).toContain("seed-icl-2.0（按账号实际资源填写）");
    expect(markup).toContain('value="account-specific-resource"');
    const apiField = markup.match(/新鉴权 API Key[\s\S]*?<\/label>/)?.[0];
    expect(apiField).toContain("● 已配置");
    expect(apiField).toContain('type="password"');
    expect(apiField).toContain('value=""');
    expect(markup).not.toContain("应用 ID");
    expect(markup).not.toContain("访问令牌");
  });



  it("converts readable speed multipliers to backend speech-rate integers", () => {
    expect(
      createSettingsPayload(
        {
          voice_provider: "byte_ws",
          voice_speed_multiplier: "1.2",
        },
        {},
      ),
    ).toMatchObject({ voice_speech_rate: 20 });
    expect(
      createSettingsPayload(
        {
          voice_provider: "byte_ws",
          voice_speed_multiplier: "1.3",
        },
        {},
      ),
    ).toMatchObject({ voice_speech_rate: 30 });
    expect(
      createSettingsPayload(
        {
          voice_provider: "byte_ws",
          voice_speed_multiplier: "1.4",
        },
        {},
      ),
    ).toMatchObject({ voice_speech_rate: 40 });
    expect(
      createSettingsPayload(
        {
          voice_provider: "byte_ws",
          voice_speed_multiplier: "",
          voice_speech_rate: 18,
        },
        {},
      ),
    ).toMatchObject({ voice_speech_rate: 18 });
  });

  it("shows style presets without overwriting existing custom style", () => {
    const customStyle = "这是我已经保存的自定义讲述方式，不能被预设覆盖。";
    const customMarkup = renderVoiceSettings({
      ...voiceProviderPatch("byte_ws"),
      voice_style: customStyle,
      voice_speech_rate: 30,
    });
    expect(customMarkup).toContain('aria-label="情感风格预设"');
    expect(customMarkup).toContain('value="custom" selected=""');
    expect(customMarkup).toContain(customStyle);
    expect(customMarkup).toContain('value="1.3"');
    expect(customMarkup).toContain('value="1.2"');
    expect(customMarkup).toContain('value="1.4"');
    expect(customMarkup).toContain('value="speech"');
    expect(customMarkup).toContain('演讲（情感丰富）');

    const presetStyle =
      "保持热情和兴奋感，语气明亮，重点词上扬，节奏略快但吐字清楚。";
    const presetMarkup = renderVoiceSettings({
      ...voiceProviderPatch("byte_ws"),
      voice_style: presetStyle,
    });
    expect(presetMarkup).toContain('value="enthusiastic" selected=""');

    const forcedCustomMarkup = renderVoiceSettings({
      ...voiceProviderPatch("byte_ws"),
      voice_style: presetStyle,
      voice_style_preset: "custom",
    });
    expect(forcedCustomMarkup).toContain('value="custom" selected=""');
    expect(forcedCustomMarkup).toContain(presetStyle);
    expect(createSettingsPayload(
      {
        voice_provider: "byte_ws",
        voice_style: presetStyle,
      },
      {},
    )).toMatchObject({ voice_style: presetStyle });
  });

  it("clears hidden WebSocket performance values when switching to HTTP", () => {
    const values: Settings = {
      ...voiceProviderPatch("byte_ws"),
      voice_model: "seed-tts-2.0-expressive",
      voice_style: "像面对观众讲解，重点处加重",
      voice_speech_rate: 18,
      ...voiceProviderPatch("byte_http"),
    };

    expect(createSettingsPayload(values, {})).toEqual({
      voice_provider: "byte_http",
      voice_endpoint: httpEndpoint,
      voice_style: "",
      voice_speech_rate: 0,
    });
    expect(voiceProviderPatch("none")).toEqual({ voice_provider: "none" });
  });

  it("retains HTTP legacy fields and reports each credential independently of aggregate readiness", () => {
    const values: Settings = {
      ...voiceProviderPatch("byte_http"),
      voice_api_key_configured: false,
      voice_access_token_configured: true,
      voice_configured: true,
    };
    const markup = renderVoiceSettings(values);
    expect(markup).toContain('value="byte_http" selected=""');
    expect(markup).toContain(`value="${httpEndpoint}"`);
    expect(markup).toContain("应用 ID");
    expect(markup.match(/访问令牌[\s\S]*?<\/label>/)?.[0]).toContain(
      "● 已配置",
    );
    expect(markup.match(/新鉴权 API Key[\s\S]*?<\/label>/)?.[0]).toContain(
      "○ 未配置",
    );
    expect(markup).not.toContain('aria-label="语音合成模型"');
    expect(markup).not.toContain('aria-label="情感与讲述风格"');
    expect(markup).not.toContain('aria-label="情感风格预设"');
    expect(markup).not.toContain('aria-label="语速（倍速）"');
    const payload = createSettingsPayload(
      {
        ...values,
        voice_app_id: "legacy-app-id",
        voice_access_token: "updated-test-token",
        voice_api_key: "",
        voice_model: "retained-ws-model",
      },
      {},
    );
    expect(payload).toEqual({
      voice_provider: "byte_http",
      voice_endpoint: httpEndpoint,
      voice_app_id: "legacy-app-id",
      voice_access_token: "updated-test-token",
      voice_style: "",
      voice_speech_rate: 0,
    });
  });
});
