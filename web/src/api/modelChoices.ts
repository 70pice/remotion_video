import type { ModelCatalog } from "./types";

export const defaultModelChoice = "default";
export const customModelChoice = "custom";
const catalogPrefix = "catalog:";

export function formatModelCacheTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "未知";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "medium",
    hour12: false,
  }).format(date);
}

// UI choice values have their own namespace; provider IDs remain opaque strings.
export function catalogModelChoice(id: string): string {
  return `${catalogPrefix}${id}`;
}

export function selectedModelChoice(
  model: string,
  catalog: ModelCatalog | undefined,
  useCustom = false,
): string {
  if (useCustom) return customModelChoice;
  if (model === "") return defaultModelChoice;
  return catalog?.models.some((entry) => entry.id === model)
    ? catalogModelChoice(model)
    : customModelChoice;
}

export function modelFromChoice(choice: string, currentModel: string): string {
  if (choice === defaultModelChoice) return "";
  if (choice === customModelChoice) return currentModel;
  if (choice.startsWith(catalogPrefix))
    return choice.slice(catalogPrefix.length);
  return currentModel;
}
