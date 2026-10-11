// Shared by the Remotion browser bundle and the Node renderer. This module has
// no Node dependencies so validation is identical at both entry points.
import componentManifest from '../../videoagents/component-manifest.json' with {type: 'json'};
import componentSetCapabilities from '../../videoagents/component-set-capabilities.json' with {type: 'json'};
import nativeComponentCapabilities from '../../videoagents/native-component-capabilities.json' with {type: 'json'};

export const productionComponentIds = Object.freeze(
  componentManifest.entries.map((entry) => entry.component_id),
);
export const semanticComponentIds = Object.freeze(
  componentManifest.entries.filter((entry) => entry.kind === 'adapter').map((entry) => entry.component_id),
);
export const communityComponentIds = Object.freeze(
  componentManifest.entries.filter((entry) => entry.kind === 'preset').map((entry) => entry.component_id),
);
const communityComponentIdSet = new Set(communityComponentIds);
const layerComponentRoles = new Map(
  nativeComponentCapabilities.entries
    .map((entry) => [entry.component_id, new Set((entry.roles ?? []).filter((role) => role === 'title' || role === 'emphasis'))])
    .filter(([, roles]) => roles.size),
);
const layerPropKeys = ['items', 'before', 'highlight', 'after', 'from_text', 'to_text'];
const nativeMinimumVisibleFrames = new Map(nativeComponentCapabilities.entries
  .filter((entry) => Number.isSafeInteger(entry.content_constraints?.min_visible_frames))
  .map((entry) => [entry.component_id, entry.content_constraints.min_visible_frames]));
const nativeSelectionComponents = new Set(nativeComponentCapabilities.entries
  .filter((entry) => entry.content_constraints?.selection_matches_item)
  .map((entry) => entry.component_id));
const focusPropKeys = ['focus_steps', 'focus_source_size'];
const noMaterialSetMainComponents = {B01: 'Rve-QuoteCard', B02: 'keyword', B03: 'Rve-SplitScreen',
  B04: 'Rve-StatCounter', B05: 'Rve-ProgressSteps', B06: 'conclusion',
  B07: 'Rve-ChartAnimation', B08: 'Rve-StatCounter', B09: 'Rve-ComparisonChart',
  B10: 'Rve-ChartAnimation', B11: 'Rve-ProgressSteps', B12: 'Rve-QuoteCard',
  B13: 'Rve-SplitScreen', B14: 'Snapcn-AnswerStream', B15: 'Rve-QuoteCard',
  B16: 'Rve-ProgressSteps', B17: 'Bits-ChatConversation', B18: 'Rve-ComparisonChart'};
export const materialRichSetComponents = Object.freeze({
  A07: ['Talkcraft-slow-push-in', 'Snapcn-TextReveal', 'Snapcn-TextHighlight', 'Rve-QuoteCard', 'Rve-ProgressSteps', 'Snapcn-WordFlip', 'Talkcraft-source-converge'],
  A08: ['Snapcn-PhoneFrame', 'Snapcn-TextReveal', 'Snapcn-TextHighlight', 'Rve-ProgressSteps', 'Rve-SplitScreen', 'Snapcn-WordFlip', 'Talkcraft-source-converge'],
  A09: ['Snapcn-PhoneFrame', 'Snapcn-TextReveal', 'Snapcn-TextHighlight', 'Rve-ProgressSteps', 'Rve-StatCounter', 'Snapcn-TextBuild', 'Snapcn-TextSwap'],
  A10: ['Talkcraft-scanline-annotate', 'Snapcn-TextReveal', 'Talkcraft-ink-underline', 'Rve-ChartAnimation', 'Rve-StatCounter', 'Snapcn-TextBuild', 'Rve-LineChart'],
  A11: ['Talkcraft-tilt-3d-page', 'Snapcn-TextReveal', 'Snapcn-TextHighlight', 'Rve-QuoteCard', 'Snapcn-WordFlip', 'Talkcraft-source-converge', 'Talkcraft-ink-underline'],
  A12: ['Talkcraft-slow-pull-reveal', 'Snapcn-TextReveal', 'Snapcn-TextHighlight', 'Rve-SplitScreen', 'Rve-ProgressSteps', 'Talkcraft-source-converge', 'Snapcn-WordFlip'],
});
const materialRichSetMainComponents = Object.freeze(Object.fromEntries(
  Object.entries(materialRichSetComponents).map(([setId, ids]) => [setId, ids[0]]),
));
export const materialRichSetIds = Object.freeze(Object.keys(materialRichSetComponents));
export const materialRichNativeIdsForSet = (setId) => materialRichSetComponents[setId] ?? [];
const expandedNoMaterialSetIds = new Set(['B07', 'B08', 'B09', 'B10', 'B11', 'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18']);
const expandedRichRules = {
  B07: {items: 3, numeric: 3, metric: 'sum'}, B08: {items: 3, numeric: 3, metric: 'sum'},
  B09: {items: 2, numeric: 2, metric: 'difference'}, B10: {items: 3, numeric: 3, metric: 'sum'},
  B11: {items: 3, supporting: 3, metric: 'items'}, B12: {items: 3, supporting: 3, metric: 'items'},
  B13: {items: 2, supporting: 3, metric: 'supporting'}, B14: {items: 3, supporting: 2, metric: 'items'},
  B15: {items: 3, supporting: 3, numeric: 3, metric: 'sum'},
  B16: {items: 3, supporting: 3, metric: 'items'}, B17: {items: 3, supporting: 2, metric: 'items'},
  B18: {items: 2, supporting: 3, numeric: 2, metric: 'supportingAndMaximum'},
};
const communityPresetPropKeys = ['content_mode', 'asset_fit', 'asset_crop', 'start_seconds', 'end_seconds', 'items', 'metric', 'tutorial_steps', 'tutorial_source_size', ...focusPropKeys];
const productionSetCapabilitiesById = new Map(componentSetCapabilities.sets.map((entry) => [entry.set_id, entry]));
const productionSetIds = new Set(componentSetCapabilities.sets.map((entry) => entry.set_id));

const fail = (message) => { throw new Error(`Timeline validation: ${message}`); };
const object = (value, name) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(`${name} must be an object`);
  return value;
};
const keys = (value, allowed, name) => {
  for (const key of Object.keys(value)) if (!allowed.includes(key)) fail(`${name}.${key} is unsupported`);
};
const integer = (value, name, minimum, maximum) => {
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    fail(`${name} must be an integer from ${minimum} to ${maximum}`);
  }
};
const text = (value, name, maximum, required = false) => {
  if (typeof value !== 'string' || [...value].length > maximum || (required && !value.trim())) {
    fail(`${name} must be ${required ? 'nonempty ' : ''}text of at most ${maximum} characters`);
  }
  if ([...value].some((character) => {
    const code = character.codePointAt(0);
    return code < 32 && code !== 9 && code !== 10 && code !== 13;
  })) fail(`${name} contains control characters`);
};
const optionalText = (value, name, maximum) => {
  if (value !== undefined) text(value, name, maximum, true);
};
const fraction = (value, name) => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) {
    fail(`${name} must be a number between 0 and 1`);
  }
};
const normalizedRect = (value, name, subject) => {
  const rect = object(value, name);
  keys(rect, ['x', 'y', 'width', 'height'], name);
  for (const field of ['x', 'y', 'width', 'height']) fraction(rect[field], `${name}.${field}`);
  if (rect.width === 0 || rect.height === 0 || rect.x + rect.width > 1 || rect.y + rect.height > 1) {
    fail(`${name} must be a nonempty rectangle inside the ${subject}`);
  }
};
const seconds = (value, name) => {
  if (value !== undefined && (typeof value !== 'number' || !Number.isFinite(value) || value < 0)) {
    fail(`${name} must be a nonnegative number of seconds`);
  }
};

const asciiCountWithUnit = (value) => typeof value === 'string' && /^([0-9]{1,5})([\u4e00-\u9fff]{1,2})$/u.test(value);
const parseAsciiCountWithUnit = (value, name) => {
  if (!asciiCountWithUnit(value)) fail(`${name} must be an ASCII integer from 0..99999 plus 1 to 2 Han unit characters`);
  const match = value.match(/^([0-9]{1,5})([\u4e00-\u9fff]{1,2})$/u);
  return {value: Number(match[1]), unit: match[2]};
};
const validateRichTextArray = (value, name, count, maximum = 24, totalMaximum = 64) => {
  if (!Array.isArray(value) || (Array.isArray(count) ? !count.includes(value.length) : value.length !== count)) {
    fail(`${name} item count is incorrect`);
  }
  value.forEach((item, index) => text(item, `${name}[${index}]`, maximum, true));
  if (value.reduce((total, item) => total + [...item].length, 0) > totalMaximum) {
    fail(`${name} must contain at most ${totalMaximum} total characters`);
  }
  return value;
};
const validateRichNumericItems = (value, name, count) => {
  const items = validateRichTextArray(value, name, count, 24, 64);
  return items.map((item, index) => {
    const pieces = item.split(/[：:]/).map((piece) => piece.trim()).filter(Boolean);
    if (pieces.length !== 2) fail(`${name}[${index}] must be label:value`);
    text(pieces[0], `${name}[${index}].label`, 16, true);
    return {label: pieces[0], ...parseAsciiCountWithUnit(pieces[1], `${name}[${index}].value`)};
  });
};
const validateRichMetric = (value, name) => {
  const metric = object(value, name);
  keys(metric, ['label', 'value', 'detail'], name);
  text(metric.label, `${name}.label`, 24, true);
  const parsed = parseAsciiCountWithUnit(metric.value, `${name}.value`);
  optionalText(metric.detail, `${name}.detail`, 32);
  return {...metric, ...parsed};
};
const validateRichNoMaterialContent = (shot, name, setId, fps) => {
  if (shot.props.composition !== 'rich') return false;
  const duration = shot.end_frame - shot.start_frame;
  if (duration < fps * 12 || duration > fps * 20) fail(`${name}: rich no-material sets require 12 to 20 seconds`);
  text(shot.title, `${name}.title`, 18, true);
  text(shot.body, `${name}.body`, 60);
  const content = object(shot.props.rich_content, `${name}.props.rich_content`);
  const allowed = {
    B01: ['takeaway', 'items', 'metric'], B02: ['takeaway', 'items', 'metric'],
    B03: ['takeaway', 'items', 'numeric_items'], B04: ['takeaway', 'metric', 'numeric_items'],
    B05: ['takeaway', 'items', 'supporting_items', 'metric'],
    B06: ['takeaway', 'items', 'supporting_items', 'metric'],
  }[setId] ?? (expandedNoMaterialSetIds.has(setId)
    ? ['takeaway', 'items', 'metric', ...(expandedRichRules[setId].supporting ? ['supporting_items'] : []),
      ...(expandedRichRules[setId].numeric ? ['numeric_items'] : [])]
    : undefined);
  if (!allowed) fail(`${name}: rich composition is only supported for B no-material sets`);
  keys(content, allowed, `${name}.props.rich_content`);
  text(content.takeaway, `${name}.props.rich_content.takeaway`, 18, true);
  if (setId === 'B02' && shot.props.keyword !== content.takeaway) fail(`${name}: B02 rich keyword must match takeaway`);
  if ((setId === 'B03' || setId === 'B05') && JSON.stringify(shot.props.items) !== JSON.stringify(content.items)) {
    fail(`${name}: rich props.items must match rich_content.items`);
  }
  if (setId === 'B04') {
    const coreMetric = shot.props.metric && typeof shot.props.metric === 'object' ? shot.props.metric : null;
    if (!coreMetric || coreMetric.label !== content.metric?.label || coreMetric.value !== content.metric?.value ||
        (coreMetric.detail ?? undefined) !== (content.metric?.detail ?? undefined)) {
      fail(`${name}: rich props.metric must match rich_content.metric`);
    }
  }
  if (setId === 'B06' && shot.props.call_to_action !== content.takeaway) fail(`${name}: B06 rich call_to_action must match takeaway`);
  if (['B01', 'B02', 'B05'].includes(setId)) {
    const items = validateRichTextArray(content.items, `${name}.props.rich_content.items`, 3);
    const metric = validateRichMetric(content.metric, `${name}.props.rich_content.metric`);
    if (metric.value !== items.length) fail(`${name}: rich metric value must equal item count`);
    if (setId === 'B05') validateRichTextArray(content.supporting_items, `${name}.props.rich_content.supporting_items`, 3, 32, 96);
  } else if (setId === 'B03') {
    validateRichTextArray(content.items, `${name}.props.rich_content.items`, 2, 32, 64);
    validateRichNumericItems(content.numeric_items, `${name}.props.rich_content.numeric_items`, 2);
    if (content.metric !== undefined) fail(`${name}: B03 rich content does not accept metric`);
  } else if (setId === 'B04') {
    const metric = validateRichMetric(content.metric, `${name}.props.rich_content.metric`);
    const numericItems = validateRichNumericItems(content.numeric_items, `${name}.props.rich_content.numeric_items`, 3);
    if (!numericItems.every((item) => item.unit === metric.unit) || numericItems.reduce((total, item) => total + item.value, 0) !== metric.value) {
      fail(`${name}: B04 rich numeric_items must sum to metric.value`);
    }
  } else if (setId === 'B06') {
    const items = validateRichTextArray(content.items, `${name}.props.rich_content.items`, [2, 3]);
    validateRichTextArray(content.supporting_items, `${name}.props.rich_content.supporting_items`, 2, 32, 64);
    const metric = validateRichMetric(content.metric, `${name}.props.rich_content.metric`);
    if (metric.value !== items.length) fail(`${name}: rich metric value must equal action item count`);
  } else if (expandedNoMaterialSetIds.has(setId)) {
    const rule = expandedRichRules[setId];
    const items = validateRichTextArray(content.items, `${name}.props.rich_content.items`, rule.items, 24, 64);
    const support = rule.supporting ? validateRichTextArray(content.supporting_items,
      `${name}.props.rich_content.supporting_items`, rule.supporting, 32, rule.supporting * 32) : [];
    const metric = validateRichMetric(content.metric, `${name}.props.rich_content.metric`);
    const numbers = rule.numeric ? validateRichNumericItems(content.numeric_items,
      `${name}.props.rich_content.numeric_items`, rule.numeric) : [];
    if (numbers.length && !numbers.every((item) => item.unit === metric.unit)) {
      fail(`${name}: expanded numeric and metric units must match`);
    }
    if (rule.metric === 'sum' && numbers.reduce((sum, item) => sum + item.value, 0) !== metric.value) {
      fail(`${name}: expanded numeric_items must sum to metric.value`);
    }
    if (rule.metric === 'difference' && Math.abs(numbers[1].value - numbers[0].value) !== metric.value) {
      fail(`${name}: expanded metric value must equal numeric difference`);
    }
    if (rule.metric === 'items' && metric.value !== items.length) {
      fail(`${name}: expanded rich metric value must equal item count`);
    }
    if (['supporting', 'supportingAndMaximum'].includes(rule.metric) && metric.value !== support.length) {
      fail(`${name}: expanded rich metric value must equal supporting item count`);
    }
    if (rule.metric === 'supportingAndMaximum' && metric.value !== Math.max(...numbers.map((item) => item.value))) {
      fail(`${name}: expanded metric value must equal maximum numeric step count`);
    }
  }
  return true;
};
const validateMaterialRichContent = (shot, name, setId, fps, timeline) => {
  if (shot.props.composition !== 'rich') fail(`${name}: material component_set requires rich composition`);
  if (timeline.presentation !== 'component_sample' || timeline.height <= timeline.width || !shot.asset_src) {
    fail(`${name}: material rich sets require a portrait silent component sample with media`);
  }
  text(shot.source_label, `${name}.source_label`, 80, true);
  const duration = shot.end_frame - shot.start_frame;
  if (duration < fps * 12 || duration > fps * 20) fail(`${name}: material rich sets require 12 to 20 seconds`);
  const main = materialRichSetMainComponents[setId];
  if (shot.component_id !== main) fail(`${name}: material component_set must match its registered main component`);
  const videoSet = setId === 'A09';
  if (videoSet ? !/\.mp4$/i.test(shot.asset_src) : !/\.(png|jpe?g|webp)$/i.test(shot.asset_src)) {
    fail(`${name}: ${setId} requires ${videoSet ? 'an MP4 operation recording' : 'an image material'}`);
  }
  text(shot.title, `${name}.title`, 18, true);
  text(shot.body, `${name}.body`, 60, true);
  const content = object(shot.props.rich_content, `${name}.props.rich_content`);
  const allowed = setId === 'A10' ? ['title', 'body', 'takeaway', 'items', 'metric', 'numeric_items'] :
    setId === 'A09' ? ['title', 'body', 'takeaway', 'items', 'supporting_items', 'metric'] :
      ['title', 'body', 'takeaway', 'items', 'supporting_items'];
  keys(content, allowed, `${name}.props.rich_content`);
  text(content.title, `${name}.props.rich_content.title`, 18, true);
  text(content.body, `${name}.props.rich_content.body`, 60, true);
  if (content.title !== shot.title || content.body !== shot.body) fail(`${name}: rich_content title/body must match shot title/body`);
  text(content.takeaway, `${name}.props.rich_content.takeaway`, 18, true);
  const items = validateRichTextArray(content.items, `${name}.props.rich_content.items`, 3, 18, 60);
  if (setId !== 'A10') validateRichTextArray(content.supporting_items, `${name}.props.rich_content.supporting_items`, 3, 18, 60);
  if (setId === 'A10') {
    const metric = validateRichMetric(content.metric, `${name}.props.rich_content.metric`);
    const numbers = validateRichNumericItems(content.numeric_items, `${name}.props.rich_content.numeric_items`, 3);
    if (!numbers.every((item) => item.unit === metric.unit) || numbers.reduce((sum, item) => sum + item.value, 0) !== metric.value) {
      fail(`${name}: A10 numeric_items must sum to metric.value`);
    }
  } else if (setId === 'A09') {
    const metric = validateRichMetric(content.metric, `${name}.props.rich_content.metric`);
    if (metric.value !== items.length || metric.unit !== '步') fail(`${name}: A09 metric must equal 3 steps`);
    const size = object(shot.props.focus_source_size, `${name}.props.focus_source_size`);
    keys(size, ['width', 'height'], `${name}.props.focus_source_size`);
    integer(size.width, `${name}.props.focus_source_size.width`, 1, 16384);
    integer(size.height, `${name}.props.focus_source_size.height`, 1, 16384);
    const steps = shot.props.focus_steps;
    if (!Array.isArray(steps) || steps.length !== 3) fail(`${name}.props.focus_steps requires 3 steps`);
    let end = 0;
    steps.forEach((step, index) => {
      const stepName = `${name}.props.focus_steps[${index}]`;
      object(step, stepName);
      keys(step, ['start_frame', 'end_frame', 'instruction', 'target'], stepName);
      integer(step.start_frame, `${stepName}.start_frame`, 0, duration - 1);
      integer(step.end_frame, `${stepName}.end_frame`, 1, duration);
      if (step.start_frame !== end || step.end_frame - step.start_frame < 30) fail(`${stepName} must be contiguous and last at least 30 frames`);
      if (step.instruction !== items[index]) fail(`${stepName}.instruction must match rich_content.items[${index}]`);
      normalizedRect(step.target, `${stepName}.target`, 'source');
      end = step.end_frame;
    });
    if (end !== duration) fail(`${name}.props.focus_steps must cover the whole shot`);
  } else {
    if (content.metric !== undefined || content.numeric_items !== undefined) fail(`${name}: ${setId} rich content does not accept metric or numeric_items`);
  }
  const expectedProps = ['component_set', 'composition', 'rich_content', ...(setId === 'A09' ? ['focus_steps', 'focus_source_size'] : [])];
  keys(shot.props, expectedProps, `${name}.props`);
  const layers = shot.layers ?? [];
  const expected = materialRichSetComponents[setId];
  if (layers.length !== 2) fail(`${name}: material rich sets require title and emphasis layers`);
  const [titleLayer, emphasisLayer] = layers;
  if (titleLayer.component_id !== expected[1] || titleLayer.role !== 'title' || titleLayer.start_frame !== 0 || titleLayer.end_frame !== duration) {
    fail(`${name}: material rich title layer must match ${expected[1]} for the full shot`);
  }
  if (emphasisLayer.component_id !== expected[2] || emphasisLayer.role !== 'emphasis' ||
      emphasisLayer.start_frame < Math.floor(duration * 0.5) || emphasisLayer.end_frame !== duration) {
    fail(`${name}: material rich emphasis layer must match ${expected[2]} near the end`);
  }
  if (setId !== 'A09' && (shot.props.focus_steps !== undefined || shot.props.focus_source_size !== undefined)) {
    fail(`${name}: only A09 accepts focus steps`);
  }
  return true;
};


const validateLayerProps = (props, name) => {
  const value = object(props, name);
  keys(value, layerPropKeys, name);
  const combined = ['before', 'highlight', 'after'].map((key) => value[key]).filter((item) => item !== undefined);
  combined.forEach((item, index) => text(item, `${name}.before_highlight_after[${index}]`, 32, true));
  if (combined.reduce((total, item) => total + [...item].length, 0) > 32) {
    fail(`${name}.before/highlight/after must contain at most 32 total characters`);
  }
  for (const key of ['from_text', 'to_text']) {
    optionalText(value[key], `${name}.${key}`, 32);
  }
  if (value.items !== undefined) {
    if (!Array.isArray(value.items) || value.items.length < 1 || value.items.length > 4) {
      fail(`${name}.items requires 1 to 4 supplied text items`);
    }
    value.items.forEach((item, index) => text(item, `${name}.items[${index}]`, 64, true));
    if (value.items.reduce((total, item) => total + [...item].length, 0) > 64) {
      fail(`${name}.items must contain at most 64 total characters`);
    }
  }
};

const rangesOverlap = (left, right) => Math.min(left.end_frame, right.end_frame) > Math.max(left.start_frame, right.start_frame);
const validateNativeSelection = (value, name) => {
  if (!nativeSelectionComponents.has(value.component_id)) return;
  const normalize = (text) => text.replace(/[^\p{L}\p{N}]+/gu, '').toLowerCase();
  const target = normalize(value.props?.highlight?.trim() || value.title.trim());
  const matches = (value.props?.items ?? []).slice(0, 5).filter((item) => normalize(item.trim()) === target);
  if (!target || matches.length !== 1) fail(`${name}: title or props.highlight must exactly match one unique option`);
};

const validateLayers = (shot, name) => {
  const layers = shot.layers ?? [];
  if (!Array.isArray(layers) || layers.length > 2) fail(`${name}.layers must contain at most 2 layers`);
  const duration = shot.end_frame - shot.start_frame;
  const seenComponents = new Set();
  const previousByRole = new Map();
  layers.forEach((raw, index) => {
    const layerName = `${name}.layers[${index}]`;
    const layer = object(raw, layerName);
    keys(layer, ['component_id', 'role', 'start_frame', 'end_frame', 'title', 'body', 'accent_color', 'props'], layerName);
    if (!['title', 'emphasis'].includes(layer.role)) fail(`${layerName}.role must be title or emphasis`);
    const roles = layerComponentRoles.get(layer.component_id);
    if (!roles) {
      fail(`${layerName}.component_id must be a native layer component`);
    }
    if (!roles.has(layer.role)) {
      fail(`${layerName}.component_id does not support ${layer.role} layers`);
    }
    if (layer.component_id === shot.component_id) fail(`${layerName}.component_id duplicates the main shot component`);
    if (seenComponents.has(layer.component_id)) fail(`${layerName}.component_id is duplicated in this shot`);
    seenComponents.add(layer.component_id);
    integer(layer.start_frame, `${layerName}.start_frame`, 0, Math.max(0, duration - 1));
    integer(layer.end_frame, `${layerName}.end_frame`, 1, duration);
    if (layer.end_frame <= layer.start_frame) fail(`${layerName}.end_frame must be greater than start_frame`);
    if (layer.end_frame - layer.start_frame < 30) fail(`${layerName} must stay visible for at least 30 frames`);
    const nativeMinimum = nativeMinimumVisibleFrames.get(layer.component_id);
    if (nativeMinimum && layer.end_frame - layer.start_frame < nativeMinimum) {
      fail(`${layerName} ${layer.component_id} must stay visible for at least ${nativeMinimum} frames to finish its native reveal`);
    }
    const previous = previousByRole.get(layer.role);
    if (previous && rangesOverlap(previous, layer)) fail(`${layerName}.role overlaps another ${layer.role} layer`);
    previousByRole.set(layer.role, layer);
    text(layer.title, `${layerName}.title`, 32, true);
    text(layer.body, `${layerName}.body`, 64);
    const color = layer.accent_color ?? '#38BDF8';
    if (typeof color !== 'string' || !/^#[a-fA-F0-9]{6}$/.test(color)) fail(`${layerName}.accent_color must be a six-digit hex color`);
    validateLayerProps(layer.props ?? {}, `${layerName}.props`);
    validateNativeSelection(layer, layerName);
  });
};

const validateFocusProps = (shot, name, timeline) => {
  const props = shot.props;
  if (props.focus_steps === undefined && props.focus_source_size === undefined) return;
  if (Object.hasOwn(materialRichSetMainComponents, props.component_set)) return;
  if (!['video', 'evidence', 'image_focus', 'Talkcraft-tilt-3d-page'].includes(shot.component_id) || !shot.asset_src ||
      timeline.height <= timeline.width || timeline.presentation !== 'component_sample' || props.tutorial_steps !== undefined || props.tutorial_source_size !== undefined ||
      props.crop !== undefined || props.asset_crop !== undefined || props.highlight !== undefined || props.focal_x !== undefined || props.focal_y !== undefined ||
      (props.fit !== undefined && props.fit !== 'contain') || (props.asset_fit !== undefined && props.asset_fit !== 'contain')) {
    fail(`${name}: material focus requires a supported uncropped contain-fit source and portrait timeline`);
  }
  const size = object(props.focus_source_size, `${name}.props.focus_source_size`);
  keys(size, ['width', 'height'], `${name}.props.focus_source_size`);
  for (const field of ['width', 'height']) integer(size[field], `${name}.props.focus_source_size.${field}`, 1, 16384);
  const steps = props.focus_steps;
  if (!Array.isArray(steps) || steps.length < 1 || steps.length > 8) fail(`${name}.props.focus_steps requires 1 to 8 steps`);
  const duration = shot.end_frame - shot.start_frame;
  let end = 0;
  steps.forEach((step, index) => {
    const stepName = `${name}.props.focus_steps[${index}]`;
    object(step, stepName);
    keys(step, ['start_frame', 'end_frame', 'instruction', 'target'], stepName);
    integer(step.start_frame, `${stepName}.start_frame`, 0, duration - 1);
    integer(step.end_frame, `${stepName}.end_frame`, 1, duration);
    if (step.start_frame !== end || step.end_frame - step.start_frame < 30) fail(`${stepName} must be contiguous and last at least 30 frames`);
    text(step.instruction, `${stepName}.instruction`, 24, true);
    normalizedRect(step.target, `${stepName}.target`, 'source');
    end = step.end_frame;
  });
  if (end !== duration) fail(`${name}.props.focus_steps must cover the whole shot`);
  const layers = shot.layers ?? [];
  if (layers.length !== 1 || layers[0].component_id !== 'Snapcn-TextReveal' || layers[0].role !== 'title' ||
      layers[0].start_frame !== 0 || layers[0].end_frame !== duration || layers[0].title !== steps[0].instruction) {
    fail(`${name}: material focus requires one full-duration native title matching the first instruction`);
  }
};

const validateCommunityPresetProps = (shot, name) => {
  const props = object(shot.props, `${name}.props`);
  keys(props, communityPresetPropKeys, `${name}.props`);
  if (props.content_mode !== undefined && !['auto', 'media', 'list', 'metric'].includes(props.content_mode)) {
    fail(`${name}.props.content_mode must be auto, media, list or metric`);
  }
  if (props.asset_fit !== undefined && !['contain', 'cover'].includes(props.asset_fit)) {
    fail(`${name}.props.asset_fit must be contain or cover`);
  }
  if (props.asset_crop !== undefined) {
    normalizedRect(props.asset_crop, `${name}.props.asset_crop`, 'asset');
  }
  seconds(props.start_seconds, `${name}.props.start_seconds`);
  seconds(props.end_seconds, `${name}.props.end_seconds`);
  const start = props.start_seconds ?? 0;
  if (props.end_seconds !== undefined && props.end_seconds <= start) {
    fail(`${name}.props.end_seconds must be greater than start_seconds`);
  }
  if (props.tutorial_steps !== undefined || props.tutorial_source_size !== undefined) {
    if (shot.component_id !== 'Snapcn-PhoneFrame' || !/\.mp4$/i.test(shot.asset_src ?? '') ||
        props.content_mode !== 'media' || props.asset_fit !== 'contain' || props.asset_crop !== undefined) {
      fail(`${name}: guided tutorials require PhoneFrame with an uncropped contain-fit MP4`);
    }
    const size = object(props.tutorial_source_size, `${name}.props.tutorial_source_size`);
    keys(size, ['width', 'height'], `${name}.props.tutorial_source_size`);
    for (const field of ['width', 'height']) integer(size[field], `${name}.props.tutorial_source_size.${field}`, 1, 16384);
    if (size.height <= size.width) fail(`${name}.props.tutorial_source_size must be portrait`);
    const steps = props.tutorial_steps;
    if (!Array.isArray(steps) || steps.length < 1 || steps.length > 8) fail(`${name}.props.tutorial_steps requires 1 to 8 steps`);
    const duration = shot.end_frame - shot.start_frame;
    let end = 0;
    steps.forEach((step, index) => {
      const stepName = `${name}.props.tutorial_steps[${index}]`;
      object(step, stepName);
      keys(step, ['start_frame', 'end_frame', 'instruction', 'target'], stepName);
      integer(step.start_frame, `${stepName}.start_frame`, 0, duration - 1);
      integer(step.end_frame, `${stepName}.end_frame`, 1, duration);
      if (step.start_frame !== end || step.end_frame - step.start_frame < 30) {
        fail(`${stepName} must follow the previous step and last at least 30 frames`);
      }
      text(step.instruction, `${stepName}.instruction`, 24, true);
      normalizedRect(step.target, `${stepName}.target`, 'source');
      end = step.end_frame;
    });
    if (end !== duration) fail(`${name}.props.tutorial_steps must cover the whole shot`);
    const layers = shot.layers ?? [];
    if (layers.length !== 1 || layers[0].component_id !== 'Snapcn-TextReveal' || layers[0].role !== 'title' ||
        layers[0].start_frame !== 0 || layers[0].end_frame !== duration || layers[0].title !== steps[0].instruction) {
      fail(`${name}: guided tutorials require one full-duration native title matching the first instruction`);
    }
  }
  if (props.items !== undefined) {
    if (!Array.isArray(props.items) || props.items.length < 1 || props.items.length > 4) {
      fail(`${name}.props.items requires 1 to 4 supplied text items`);
    }
    props.items.forEach((item, index) => text(item, `${name}.props.items[${index}]`, 64, true));
  }
  if (props.metric !== undefined) {
    const metric = object(props.metric, `${name}.props.metric`);
    keys(metric, ['label', 'value', 'detail'], `${name}.props.metric`);
    text(metric.label, `${name}.props.metric.label`, 48, true);
    text(metric.value, `${name}.props.metric.value`, 40, true);
    optionalText(metric.detail, `${name}.props.metric.detail`, 64);
  }
};

const componentSetPartText = (shot, content, binding) => {
  if (binding === 'title') return shot.title ?? '';
  if (binding === 'body') return shot.body ?? '';
  if (binding === 'media') return '';
  let value = content;
  for (const key of binding.split('.')) {
    if (value && typeof value === 'object' && !Array.isArray(value)) value = value[key];
    else if (Array.isArray(value) && /^\d+$/.test(key)) value = value[Number(key)];
    else return '';
  }
  if (Array.isArray(value)) return value.join(' ');
  if (value && typeof value === 'object') return Object.values(value).filter(Boolean).join(' ');
  return String(value ?? '');
};

const validateSetDesignSourceRefs = (refs, name) => {
  if (refs === undefined) return;
  if (!Array.isArray(refs) || refs.length > 30) fail(`${name} requires at most 30 source refs`);
  refs.forEach((ref, index) => text(ref, `${name}[${index}]`, 3000, true));
};

const validateProductionRichContent = (shot, content, name, setId) => {
  const value = object(content, name);
  if (Object.hasOwn(value, 'title') || Object.hasOwn(value, 'body')) fail(`${name} must not duplicate shot title/body`);
  const sourceRefs = value.source_refs;
  const rich = {...value};
  delete rich.source_refs;
  validateSetDesignSourceRefs(sourceRefs, `${name}.source_refs`);
  text(rich.takeaway, `${name}.takeaway`, setId.startsWith('A') && Number(setId.slice(1)) >= 7 ? 18 : 32, true);
  if (['A07', 'A08', 'A11', 'A12'].includes(setId)) {
    keys(value, ['takeaway', 'items', 'supporting_items', 'source_refs'], name);
    validateRichTextArray(rich.items, `${name}.items`, 3, 24, 64);
    validateRichTextArray(rich.supporting_items, `${name}.supporting_items`, 3, 24, 64);
  } else if (setId === 'A09') {
    keys(value, ['takeaway', 'items', 'supporting_items', 'metric', 'source_refs'], name);
    const items = validateRichTextArray(rich.items, `${name}.items`, 3, 24, 64);
    validateRichTextArray(rich.supporting_items, `${name}.supporting_items`, 3, 24, 64);
    const metric = validateRichMetric(rich.metric, `${name}.metric`);
    if (metric.value !== items.length) fail(`${name}: A09 metric must equal 3 items`);
  } else if (setId === 'A10') {
    keys(value, ['takeaway', 'items', 'metric', 'numeric_items', 'source_refs'], name);
    validateRichTextArray(rich.items, `${name}.items`, 3, 18, 60);
    const metric = validateRichMetric(rich.metric, `${name}.metric`);
    const numbers = validateRichNumericItems(rich.numeric_items, `${name}.numeric_items`, 3);
    if (!numbers.every((item) => item.unit === metric.unit) || numbers.reduce((sum, item) => sum + item.value, 0) !== metric.value) {
      fail(`${name}: A10 numeric_items must sum to metric.value`);
    }
  } else if (Object.hasOwn(expandedRichRules, setId) || ['B01', 'B02', 'B03', 'B04', 'B05', 'B06'].includes(setId)) {
    const allowed = {
      B01: ['takeaway', 'items', 'metric', 'source_refs'], B02: ['takeaway', 'items', 'metric', 'source_refs'],
      B03: ['takeaway', 'items', 'numeric_items', 'source_refs'], B04: ['takeaway', 'metric', 'numeric_items', 'source_refs'],
      B05: ['takeaway', 'items', 'supporting_items', 'metric', 'source_refs'],
      B06: ['takeaway', 'items', 'supporting_items', 'metric', 'source_refs'],
    }[setId] ?? ['takeaway', 'items', 'metric', ...(expandedRichRules[setId].supporting ? ['supporting_items'] : []),
      ...(expandedRichRules[setId].numeric ? ['numeric_items'] : []), 'source_refs'];
    keys(value, allowed, name);
    if (['B01', 'B02', 'B05'].includes(setId)) {
      const items = validateRichTextArray(rich.items, `${name}.items`, 3);
      const metric = validateRichMetric(rich.metric, `${name}.metric`);
      if (metric.value !== items.length) fail(`${name}: rich metric value must equal item count`);
      if (setId === 'B05') validateRichTextArray(rich.supporting_items, `${name}.supporting_items`, 3, 32, 96);
    } else if (setId === 'B03') {
      validateRichTextArray(rich.items, `${name}.items`, 2, 32, 64);
      validateRichNumericItems(rich.numeric_items, `${name}.numeric_items`, 2);
      if (rich.metric !== undefined) fail(`${name}: B03 rich content does not accept metric`);
    } else if (setId === 'B04') {
      const metric = validateRichMetric(rich.metric, `${name}.metric`);
      const numbers = validateRichNumericItems(rich.numeric_items, `${name}.numeric_items`, 3);
      if (!numbers.every((item) => item.unit === metric.unit) || numbers.reduce((sum, item) => sum + item.value, 0) !== metric.value) {
        fail(`${name}: B04 rich numeric_items must sum to metric.value`);
      }
    } else if (setId === 'B06') {
      const items = validateRichTextArray(rich.items, `${name}.items`, [2, 3]);
      validateRichTextArray(rich.supporting_items, `${name}.supporting_items`, 2, 32, 64);
      const metric = validateRichMetric(rich.metric, `${name}.metric`);
      if (metric.value !== items.length) fail(`${name}: rich metric value must equal action item count`);
    } else {
      const rule = expandedRichRules[setId];
      const items = validateRichTextArray(rich.items, `${name}.items`, rule.items, 24, 64);
      const support = rule.supporting ? validateRichTextArray(rich.supporting_items, `${name}.supporting_items`, rule.supporting, 32, rule.supporting * 32) : [];
      const metric = validateRichMetric(rich.metric, `${name}.metric`);
      const numbers = rule.numeric ? validateRichNumericItems(rich.numeric_items, `${name}.numeric_items`, rule.numeric) : [];
      if (numbers.length && !numbers.every((item) => item.unit === metric.unit)) fail(`${name}: expanded numeric and metric units must match`);
      if (rule.metric === 'sum' && numbers.reduce((sum, item) => sum + item.value, 0) !== metric.value) fail(`${name}: expanded numeric_items must sum to metric.value`);
      if (rule.metric === 'difference' && Math.abs(numbers[1].value - numbers[0].value) !== metric.value) fail(`${name}: expanded metric value must equal numeric difference`);
      if (rule.metric === 'items' && metric.value !== items.length) fail(`${name}: expanded rich metric value must equal item count`);
      if (['supporting', 'supportingAndMaximum'].includes(rule.metric) && metric.value !== support.length) fail(`${name}: expanded rich metric value must equal supporting item count`);
      if (rule.metric === 'supportingAndMaximum' && metric.value !== Math.max(...numbers.map((item) => item.value))) fail(`${name}: expanded metric value must equal maximum numeric step count`);
    }
  } else {
    keys(value, ['takeaway', 'items', 'supporting_items', 'metric', 'numeric_items', 'source_refs'], name);
    if (rich.items !== undefined) validateRichTextArray(rich.items, `${name}.items`, [1, 2, 3, 4], 24, 96);
    if (rich.supporting_items !== undefined) validateRichTextArray(rich.supporting_items, `${name}.supporting_items`, [1, 2, 3, 4], 32, 128);
    if (rich.metric !== undefined) validateRichMetric(rich.metric, `${name}.metric`);
    if (rich.numeric_items !== undefined) validateRichNumericItems(rich.numeric_items, `${name}.numeric_items`, [1, 2, 3, 4]);
  }
  return value;
};

const validateSetDesign = (shot, name, timeline) => {
  if (shot.set_design === undefined) return;
  if (timeline.presentation !== undefined && timeline.presentation !== 'production') fail(`${name}.set_design is only supported for production timelines`);
  if (timeline.width !== 1080 || timeline.height !== 1920 || timeline.fps !== 30) fail(`${name}.set_design requires 1080x1920 at 30fps`);
  const duration = shot.end_frame - shot.start_frame;
  const design = object(shot.set_design, `${name}.set_design`);
  keys(design, ['set_id', 'content', 'parts', 'focus_steps', 'source_size'], `${name}.set_design`);
  if (!productionSetIds.has(design.set_id)) fail(`${name}.set_design.set_id must be A01-A12 or B01-B18`);
  const setMeta = productionSetCapabilitiesById.get(design.set_id);
  if (shot.component_id !== setMeta.main_component_id) fail(`${name}.set_design main component must match ${setMeta.main_component_id}`);
  const content = validateProductionRichContent(shot, design.content, `${name}.set_design.content`, design.set_id);
  if (Array.isArray(shot.layers) && shot.layers.length) fail(`${name}.set_design cannot add layers`);
  const props = object(shot.props, `${name}.props`);
  keys(props, ['start_seconds', 'end_seconds', 'fit', 'asset_fit'], `${name}.props`);
  if (props.fit !== undefined && !['contain', 'cover'].includes(props.fit)) fail(`${name}.props.fit must be contain or cover`);
  if (props.asset_fit !== undefined && !['contain', 'cover'].includes(props.asset_fit)) fail(`${name}.props.asset_fit must be contain or cover`);
  seconds(props.start_seconds, `${name}.props.start_seconds`);
  seconds(props.end_seconds, `${name}.props.end_seconds`);
  if (props.end_seconds !== undefined && props.end_seconds <= (props.start_seconds ?? 0)) fail(`${name}.props.end_seconds must be greater than start_seconds`);
  if (setMeta.material_kind === 'none') {
    if (shot.asset_src !== null || design.focus_steps !== undefined || design.source_size !== undefined || Object.keys(props).length) fail(`${name}.set_design ${design.set_id} does not accept media`);
  } else {
    text(shot.source_label, `${name}.source_label`, 160, true);
    if (!shot.asset_src) fail(`${name}.set_design ${design.set_id} requires media`);
  }
  if (shot.asset_src) {
    const video = /\.mp4$/i.test(shot.asset_src);
    const image = /\.(png|jpe?g|webp)$/i.test(shot.asset_src);
    if (setMeta.material_kind === 'image' && !image) fail(`${name}.set_design ${design.set_id} requires image media`);
    if (setMeta.material_kind === 'video' && !video) fail(`${name}.set_design ${design.set_id} requires video media`);
    if (setMeta.material_kind === 'image_or_video' && !image && !video) fail(`${name}.set_design ${design.set_id} requires image or video media`);
    if (image && (props.start_seconds !== undefined || props.end_seconds !== undefined)) fail(`${name}: image component sets reject video trim props`);
  }
  const expected = new Map(setMeta.parts.map((part) => [part.part_id, part]));
  if (!Array.isArray(design.parts) || design.parts.length !== setMeta.parts.length) fail(`${name}.set_design.parts must include every template part`);
  const seen = new Set();
  const parts = design.parts.map((part, index) => {
    const partName = `${name}.set_design.parts[${index}]`;
    const value = object(part, partName);
    keys(value, ['part_id', 'start_frame', 'end_frame', 'box'], partName);
    const definition = expected.get(value.part_id);
    if (!definition) fail(`${partName}.part_id must match the template`);
    if (seen.has(value.part_id)) fail(`${partName}.part_id is duplicated`);
    seen.add(value.part_id);
    integer(value.start_frame, `${partName}.start_frame`, 0, Math.max(0, duration - 1));
    integer(value.end_frame, `${partName}.end_frame`, 1, duration);
    normalizedRect(value.box, `${partName}.box`, 'component-set safe area');
    const boundText = componentSetPartText(shot, content, definition.binding);
    if (definition.binding !== 'media' && !boundText.trim()) fail(`${design.set_id}.${value.part_id} is missing current content`);
    const entrance = definition.binding === 'media' ? 0 : Math.ceil(timeline.fps * 0.5);
    const minimum = entrance + Math.max(Math.ceil(timeline.fps * 1.5), Math.ceil([...boundText.replaceAll(' ', '')].length / 12 * timeline.fps));
    if (value.end_frame > duration || value.end_frame - value.start_frame < minimum) fail(`${design.set_id}.${value.part_id} display interval is too short`);
    if (value.box.width < 0.18 || value.box.height < 0.045) fail(`${design.set_id}.${value.part_id} box is too small`);
    return {...value, definition};
  });
  if (seen.size !== expected.size) fail(`${name}.set_design.parts must include every template part`);
  parts.forEach((part, index) => {
    for (const other of parts.slice(0, index)) {
      if (Math.min(part.end_frame, other.end_frame) <= Math.max(part.start_frame, other.start_frame)) continue;
      const overlapX = Math.min(part.box.x + part.box.width, other.box.x + other.box.width) - Math.max(part.box.x, other.box.x);
      const overlapY = Math.min(part.box.y + part.box.height, other.box.y + other.box.height) - Math.max(part.box.y, other.box.y);
      if (overlapX > 0.000001 && overlapY > 0.000001) fail(`${name}.set_design.parts must not overlap while visible`);
    }
  });
  if (design.source_size !== undefined) {
    const size = object(design.source_size, `${name}.set_design.source_size`);
    keys(size, ['width', 'height'], `${name}.set_design.source_size`);
    integer(size.width, `${name}.set_design.source_size.width`, 1, 16384);
    integer(size.height, `${name}.set_design.source_size.height`, 1, 16384);
  }
  if (design.set_id === 'A09' && design.focus_steps === undefined) fail(`${name}.set_design A09 requires focus_steps`);
  if (design.focus_steps !== undefined) {
    if (!setMeta.focus_supported) fail(`${name}.set_design ${design.set_id} does not support focus_steps`);
    const fit = props.fit ?? props.asset_fit ?? 'contain';
    if (fit !== 'contain') fail(`${name}.set_design focus_steps require contain fit`);
    if (design.source_size === undefined) fail(`${name}.set_design.focus_steps require source_size`);
    if (!Array.isArray(design.focus_steps) || design.focus_steps.length < 1 || design.focus_steps.length > 8) fail(`${name}.set_design.focus_steps requires 1 to 8 steps`);
    let end = 0;
    const itemTexts = Array.isArray(content.items) ? content.items : [];
    design.focus_steps.forEach((step, index) => {
      const stepName = `${name}.set_design.focus_steps[${index}]`;
      const value = object(step, stepName);
      keys(value, ['start_frame', 'end_frame', 'instruction', 'target'], stepName);
      integer(value.start_frame, `${stepName}.start_frame`, 0, Math.max(0, duration - 1));
      integer(value.end_frame, `${stepName}.end_frame`, 1, duration);
      if (value.start_frame !== end || value.end_frame - value.start_frame < 30) fail(`${stepName} must be contiguous and last at least 30 frames`);
      text(value.instruction, `${stepName}.instruction`, 24, true);
      normalizedRect(value.target, `${stepName}.target`, 'source');
      if (design.set_id === 'A09' && value.instruction !== itemTexts[index]) fail(`${stepName}.instruction must match set_design.content.items[${index}]`);
      end = value.end_frame;
    });
    if (end !== duration) fail(`${name}.set_design.focus_steps must cover the whole shot`);
  }
};

export const validateMediaSource = (source, jobId, name = 'media source') => {
  if (source === null) return;
  if (typeof source !== 'string') fail(`${name} must be a controlled local media path or null`);
  const pieces = source.split('/');
  if (pieces[0] !== 'videoagents' || pieces[1] !== jobId || pieces.length < 3 ||
      pieces.some((piece) => !/^[a-zA-Z0-9_-][a-zA-Z0-9_.-]*$/.test(piece) || piece === '.' || piece === '..') ||
      source.length > 512) {
    fail(`${name} must be videoagents/${jobId}/<file> without URLs, absolute paths or traversal`);
  }
};

const validateProps = (shot, name) => {
  const props = Object.fromEntries(Object.entries(object(shot.props, `${name}.props`))
    .filter(([key]) => !['component_set', 'composition', 'rich_content'].includes(key)));
  const validateCue = (cue, cueName) => integer(cue, cueName, 0, shot.end_frame - shot.start_frame - 15);
  const validateItemCues = (items) => {
    let previous = 0;
    items.forEach((item, index) => {
      if (item.reveal_frame !== undefined) validateCue(item.reveal_frame, `${name}.props.items[${index}].reveal_frame`);
      const cue = item.reveal_frame ?? 0;
      if (cue < previous) fail(`${name}.props.items reveal_frame must be nondecreasing; omitted cues default to 0`);
      previous = cue;
    });
  };
  if (communityComponentIdSet.has(shot.component_id)) {
    validateCommunityPresetProps({...shot, props}, name);
    return;
  }
  switch (shot.component_id) {
    case 'title':
      keys(props, ['eyebrow'], `${name}.props`);
      optionalText(props.eyebrow, `${name}.props.eyebrow`, 48);
      break;
    case 'keyword':
      keys(props, ['keyword'], `${name}.props`);
      optionalText(props.keyword, `${name}.props.keyword`, 40);
      break;
    case 'evidence': {
      keys(props, ['highlight', ...focusPropKeys], `${name}.props`);
      if (!shot.asset_src || (!shot.source_label.trim() && !props.focus_steps)) fail(`${name}: evidence requires an image and a source label`);
      if (props.highlight !== undefined) {
        normalizedRect(props.highlight, `${name}.props.highlight`, 'image');
      }
      break;
    }
    case 'image_focus':
      keys(props, ['focal_x', 'focal_y', 'crop', ...focusPropKeys], `${name}.props`);
      if (!shot.asset_src) fail(`${name}: image_focus requires an image`);
      for (const field of ['focal_x', 'focal_y']) if (props[field] !== undefined) fraction(props[field], `${name}.props.${field}`);
      if (props.crop !== undefined) {
        normalizedRect(props.crop, `${name}.props.crop`, 'image');
      }
      break;
    case 'video': {
      keys(props, ['start_seconds', 'end_seconds', 'fit', 'crop', ...focusPropKeys], `${name}.props`);
      if (!shot.asset_src || !/\.mp4$/i.test(shot.asset_src)) fail(`${name}: video requires an MP4 video asset`);
      seconds(props.start_seconds, `${name}.props.start_seconds`);
      seconds(props.end_seconds, `${name}.props.end_seconds`);
      const start = props.start_seconds ?? 0;
      if (props.end_seconds !== undefined && props.end_seconds <= start) fail(`${name}.props.end_seconds must be greater than start_seconds`);
      if (props.fit !== undefined && !['contain', 'cover'].includes(props.fit)) fail(`${name}.props.fit must be contain or cover`);
      if (props.crop !== undefined) {
        normalizedRect(props.crop, `${name}.props.crop`, 'video');
      }
      break;
    }
    case 'comparison':
      keys(props, ['left_title', 'left_body', 'right_title', 'right_body', 'right_reveal_frame'], `${name}.props`);
      for (const field of ['left_title', 'right_title']) text(props[field], `${name}.props.${field}`, 48, true);
      for (const field of ['left_body', 'right_body']) text(props[field], `${name}.props.${field}`, 160, true);
      if (props.right_reveal_frame !== undefined) validateCue(props.right_reveal_frame, `${name}.props.right_reveal_frame`);
      break;
    case 'data':
      keys(props, ['items'], `${name}.props`);
      if (!Array.isArray(props.items) || props.items.length < 1 || props.items.length > 4) fail(`${name}.props.items requires 1 to 4 supplied data items`);
      props.items.forEach((raw, index) => {
        const item = object(raw, `${name}.props.items[${index}]`);
        keys(item, ['label', 'value', 'detail', 'reveal_frame'], `${name}.props.items[${index}]`);
        text(item.label, `${name}.props.items[${index}].label`, 48, true);
        text(item.value, `${name}.props.items[${index}].value`, 40, true);
        optionalText(item.detail, `${name}.props.items[${index}].detail`, 64);
      });
      validateItemCues(props.items);
      break;
    case 'steps':
      keys(props, ['items', 'layout'], `${name}.props`);
      if (props.layout !== undefined && !['cards', 'flow'].includes(props.layout)) fail(`${name}.props.layout must be cards or flow`);
      if (!Array.isArray(props.items) || props.items.length < 1 || props.items.length > 4) fail(`${name}.props.items requires 1 to 4 supplied steps`);
      props.items.forEach((raw, index) => {
        const item = object(raw, `${name}.props.items[${index}]`);
        keys(item, ['title', 'body', 'reveal_frame'], `${name}.props.items[${index}]`);
        text(item.title, `${name}.props.items[${index}].title`, 48, true);
        optionalText(item.body, `${name}.props.items[${index}].body`, 96);
      });
      validateItemCues(props.items);
      break;
    case 'conclusion':
      keys(props, ['call_to_action'], `${name}.props`);
      optionalText(props.call_to_action, `${name}.props.call_to_action`, 72);
      break;
    default:
      fail(`${name}.component_id is not a production component`);
  }
};

export const validateTimeline = (input) => {
  const timeline = object(input, 'timeline');
  keys(timeline, ['schema_version', 'job_id', 'revision', 'width', 'height', 'fps', 'duration_in_frames', 'audio_src', 'shots', 'captions', 'presentation'], 'timeline');
  if (timeline.schema_version !== '1') fail('schema_version must be "1"');
  const presentation = timeline.presentation ?? 'production';
  if (!['production', 'component_sample'].includes(presentation)) fail('presentation must be production or component_sample');
  if (typeof timeline.job_id !== 'string' || !/^[a-zA-Z0-9_-]{1,100}$/.test(timeline.job_id)) fail('job_id must be a safe task identifier');
  integer(timeline.revision, 'revision', 1, Number.MAX_SAFE_INTEGER);
  integer(timeline.width, 'width', 240, 3840);
  integer(timeline.height, 'height', 240, 3840);
  if (timeline.width % 2 || timeline.height % 2) fail('width and height must be even for H.264');
  integer(timeline.fps, 'fps', 1, 60);
  integer(timeline.duration_in_frames, 'duration_in_frames', 1, timeline.fps * 3600);
  validateMediaSource(timeline.audio_src, timeline.job_id, 'audio_src');
  if (timeline.audio_src && !/\.(wav|mp3|m4a|aac|ogg)$/i.test(timeline.audio_src)) fail('audio_src has an unsupported audio extension');
  if (presentation === 'component_sample' && timeline.audio_src) fail('component_sample presentation must be silent without audio_src');
  if (!Array.isArray(timeline.shots) || timeline.shots.length < 1 || timeline.shots.length > 3000) fail('shots must contain 1 to 3000 shots');
  let expectedStart = 0;
  const identifiers = new Set();
  timeline.shots.forEach((raw, index) => {
    const name = `shots[${index}]`;
    const shot = object(raw, name);
    keys(shot, ['shot_id', 'start_frame', 'end_frame', 'component_id', 'title', 'body', 'asset_src', 'source_label', 'media_usage', 'accent_color', 'props', 'layers', 'set_design'], name);
    text(shot.shot_id, `${name}.shot_id`, 100, true);
    if (identifiers.has(shot.shot_id)) fail(`${name}.shot_id is duplicated`);
    identifiers.add(shot.shot_id);
    integer(shot.start_frame, `${name}.start_frame`, 0, timeline.duration_in_frames - 1);
    integer(shot.end_frame, `${name}.end_frame`, 1, timeline.duration_in_frames);
    if (shot.start_frame !== expectedStart || shot.end_frame <= shot.start_frame) fail(`${name}: shots must cover the complete timeline contiguously with no gaps or overlaps`);
    expectedStart = shot.end_frame;
    if (!productionComponentIds.includes(shot.component_id)) fail(`${name}.component_id is not supported`);
    text(shot.title, `${name}.title`, 100, true);
    text(shot.body, `${name}.body`, 240);
    text(shot.source_label, `${name}.source_label`, 160);
    if (shot.media_usage !== undefined && !['source_evidence', 'context_example'].includes(shot.media_usage)) {
      fail(`${name}.media_usage must be source_evidence or context_example`);
    }
    if (shot.media_usage === 'context_example') {
      if (!shot.asset_src || !(shot.component_id === 'image_focus' || shot.component_id === 'video' || communityComponentIdSet.has(shot.component_id))) {
        fail(`${name}: context examples require an image, video or native media component`);
      }
      if (!shot.source_label.includes('另案示例') || !/[a-z0-9-]+\.[a-z]{2,}/i.test(shot.source_label)) {
        fail(`${name}: context examples must display 另案示例 and their source domain`);
      }
    }
    if (typeof shot.accent_color !== 'string' || !/^#[a-fA-F0-9]{6}$/.test(shot.accent_color)) fail(`${name}.accent_color must be a six-digit hex color`);
    validateMediaSource(shot.asset_src, timeline.job_id, `${name}.asset_src`);
    if (shot.asset_src) {
      const acceptsVideo = shot.component_id === 'video' || communityComponentIdSet.has(shot.component_id);
      const acceptsImage = shot.component_id !== 'video';
      const valid = (acceptsVideo && /\.mp4$/i.test(shot.asset_src)) || (acceptsImage && /\.(png|jpe?g|webp)$/i.test(shot.asset_src));
      if (!valid) {
        fail(`${name}.asset_src requires ${communityComponentIdSet.has(shot.component_id) ? 'a PNG, JPEG, WebP image or MP4 video' : shot.component_id === 'video' ? 'an MP4 video' : 'a PNG, JPEG or WebP image'}`);
      }
    }
    if (shot.props.component_set !== undefined) {
      const setId = shot.props.component_set;
      if (Object.hasOwn(materialRichSetMainComponents, setId)) {
        validateMaterialRichContent(shot, name, setId, timeline.fps, timeline);
      } else {
        if (!Object.hasOwn(noMaterialSetMainComponents, setId) || noMaterialSetMainComponents[setId] !== shot.component_id) {
        fail(`${name}: no-material component_set must match its registered main component`);
        }
        if (presentation !== 'component_sample' || timeline.height <= timeline.width || shot.asset_src !== null) {
        fail(`${name}: no-material sets require a portrait silent component sample without an asset`);
        }
        if (['focus_steps', 'focus_source_size', 'tutorial_steps', 'tutorial_source_size', 'start_seconds', 'end_seconds', 'asset_crop', 'asset_fit', 'content_mode'].some((key) => shot.props[key] !== undefined)) {
        fail(`${name}: no-material sets reject media and tutorial properties`);
        }
        const expanded = expandedNoMaterialSetIds.has(setId);
        const expectedKeys = {B01: ['component_set'], B02: ['component_set', 'keyword'],
        B03: ['component_set', 'items'], B04: ['component_set', 'metric'],
        B05: ['component_set', 'items'], B06: ['component_set', 'call_to_action']}[setId] ?? (expanded ? ['component_set'] : undefined);
        const rich = shot.props.composition === 'rich';
        if (shot.props.composition !== undefined && !rich) fail(`${name}: no-material composition must be rich when supplied`);
        if (expanded && !rich) fail(`${name}: expanded no-material sets require rich composition`);
        keys(shot.props, rich ? [...expectedKeys, 'composition', 'rich_content'] : expectedKeys, `${name}.props`);
        if (expectedKeys.some((key) => shot.props[key] === undefined)) fail(`${name}: no-material set content is incomplete`);
        if (setId === 'B03' || setId === 'B05') {
        const items = shot.props.items;
        if (!Array.isArray(items) || items.length !== (setId === 'B03' ? 2 : 3)) fail(`${name}: no-material set item count is incorrect`);
        items.forEach((item, index) => text(item, `${name}.props.items[${index}]`, 32, true));
        }
        if (setId === 'B04') {
        const metric = object(shot.props.metric, `${name}.props.metric`);
        keys(metric, ['label', 'value', 'detail'], `${name}.props.metric`);
        text(metric.label, `${name}.props.metric.label`, 24, true);
        if (typeof metric.value !== 'string' || !/^[0-9]{1,5}[\u4e00-\u9fff]{1,2}$/.test(metric.value)) fail(`${name}: B04 requires an integer count and explicit unit`);
        optionalText(metric.detail, `${name}.props.metric.detail`, 32);
        }
        validateRichNoMaterialContent(shot, name, setId, timeline.fps);
      }
    }
    validateSetDesign(shot, name, timeline);
    if (shot.set_design !== undefined) return;
    validateFocusProps(shot, name, timeline);
    validateProps(shot, name);
    if (shot.props.tutorial_steps !== undefined && timeline.height <= timeline.width) {
      fail(`${name}: guided phone tutorials require a portrait timeline`);
    }
    validateNativeSelection(shot, name);
    validateLayers(shot, name);
  });
  if (expectedStart !== timeline.duration_in_frames) fail('shots must end at duration_in_frames');
  if (!Array.isArray(timeline.captions) || timeline.captions.length > 20000) fail('captions must be an array of at most 20000 segments');
  if (presentation === 'component_sample' && timeline.captions.length) fail('component_sample presentation must not include captions');
  if (timeline.captions.length && !timeline.audio_src) fail('captions require the aligned source audio');
  let previousEnd = 0;
  const durationMs = timeline.duration_in_frames / timeline.fps * 1000;
  timeline.captions.forEach((raw, index) => {
    const name = `captions[${index}]`;
    const caption = object(raw, name);
    keys(caption, ['text', 'start_ms', 'end_ms'], name);
    text(caption.text, `${name}.text`, 72, true);
    if (!Number.isFinite(caption.start_ms) || !Number.isFinite(caption.end_ms) || caption.start_ms < previousEnd ||
        caption.end_ms <= caption.start_ms || caption.end_ms > durationMs + 0.001) {
      fail(`${name}: measured caption timestamps must be ordered, nonoverlapping and inside the audio timeline`);
    }
    previousEnd = caption.end_ms;
  });
  return timeline;
};
