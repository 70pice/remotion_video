import productionBindings from '../../videoagents/production-bindings.json' with {type: 'json'};

export const communityProductionBindings = Object.freeze(productionBindings);
export const boundCommunityComponentIds = Object.freeze(Object.keys(productionBindings));

const boundSet = new Set(boundCommunityComponentIds);
const fail = (message) => { throw new Error(`Timeline validation: ${message}`); };

const isPlainObject = (value) => value && typeof value === 'object' && !Array.isArray(value);
const textLength = (value) => [...value].length;

const rejectControlCharacters = (value, name) => {
  if ([...value].some((character) => {
    const code = character.codePointAt(0);
    return code < 32 && code !== 9 && code !== 10 && code !== 13;
  })) fail(`${name} contains control characters`);
};

const validateHttpUrl = (value, name) => {
  if (typeof value !== 'string' || !value.trim()) fail(`${name} must be a nonempty HTTP/HTTPS URL`);
  let parsed;
  try {
    parsed = new globalThis.URL(value);
  } catch {
    fail(`${name} must be a nonempty HTTP/HTTPS URL`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || !parsed.hostname) {
    fail(`${name} must be a nonempty HTTP/HTTPS URL`);
  }
};

const validateSchema = (schema, value, name) => {
  if (schema.type === 'object') {
    if (!isPlainObject(value)) fail(`${name} must be an object`);
    const properties = schema.properties ?? {};
    const required = new Set(schema.required ?? []);
    for (const key of required) if (value[key] === undefined) fail(`${name}.${key} is required`);
    if (schema.additionalProperties === false) {
      for (const key of Object.keys(value)) if (!Object.hasOwn(properties, key)) fail(`${name}.${key} is unsupported`);
    }
    for (const [key, childSchema] of Object.entries(properties)) {
      if (value[key] !== undefined) validateSchema(childSchema, value[key], `${name}.${key}`);
    }
    return;
  }
  if (schema.type === 'array') {
    if (!Array.isArray(value)) fail(`${name} must be an array`);
    if (schema.minItems !== undefined && value.length < schema.minItems) fail(`${name} requires at least ${schema.minItems} items`);
    if (schema.maxItems !== undefined && value.length > schema.maxItems) fail(`${name} accepts at most ${schema.maxItems} items`);
    value.forEach((item, index) => validateSchema(schema.items, item, `${name}[${index}]`));
    return;
  }
  if (schema.type === 'string') {
    if (typeof value !== 'string') fail(`${name} must be text`);
    rejectControlCharacters(value, name);
    if (schema.minLength !== undefined && textLength(value.trim()) < schema.minLength) fail(`${name} must be nonempty text`);
    if (schema.maxLength !== undefined && textLength(value) > schema.maxLength) fail(`${name} must be text of at most ${schema.maxLength} characters`);
    if (schema.enum !== undefined && !schema.enum.includes(value)) fail(`${name} must be one of ${schema.enum.join(', ')}`);
    if (schema.pattern !== undefined && !new RegExp(schema.pattern).test(value)) fail(`${name} does not match the required pattern`);
    if (name.endsWith('.source_ref')) validateHttpUrl(value, name);
    return;
  }
  if (schema.type === 'integer' || schema.type === 'number') {
    const ok = schema.type === 'integer' ? Number.isSafeInteger(value) : typeof value === 'number';
    if (!ok || !Number.isFinite(value)) fail(`${name} must be a ${schema.type}`);
    if (schema.minimum !== undefined && value < schema.minimum) fail(`${name} must be at least ${schema.minimum}`);
    if (schema.maximum !== undefined && value > schema.maximum) fail(`${name} must be at most ${schema.maximum}`);
    return;
  }
  if (schema.type === 'boolean') {
    if (typeof value !== 'boolean') fail(`${name} must be true or false`);
    return;
  }
  fail(`${name} has unsupported schema type`);
};

export const hasBoundCommunityComponent = (componentId) => boundSet.has(componentId);

export const hasProductionCommunityProps = (shot) =>
  hasBoundCommunityComponent(shot.component_id) && isPlainObject(shot.props) && Object.keys(shot.props).length > 0;

const validateRevealFrame = (shot, name, props) => {
  if (props.reveal_frame === undefined) return;
  const duration = shot.end_frame - shot.start_frame;
  if (!Number.isSafeInteger(props.reveal_frame) || props.reveal_frame < 0 || props.reveal_frame > duration - 15) {
    fail(`${name}.props.reveal_frame must be an integer from 0 to ${duration - 15}`);
  }
};

export const validateCommunityBindingProps = (shot, name) => {
  if (!hasBoundCommunityComponent(shot.component_id)) fail(`${name}.component_id does not have a production binding`);
  if (!isPlainObject(shot.props)) fail(`${name}.props must be an object`);
  if (!Object.keys(shot.props).length) return;
  if (shot.asset_src) fail(`${name}: bound community components do not accept asset_src`);
  const binding = productionBindings[shot.component_id];
  validateSchema(binding.schema, shot.props, `${name}.props`);
  validateRevealFrame(shot, name, shot.props);
  if ((binding.chart || binding.sourced) && !shot.source_label.trim()) {
    fail(`${name}: bound sourced components require a source label`);
  }
  if (shot.component_id === 'Rve-PieChart') {
    const total = shot.props.segments.reduce((sum, segment) => sum + segment.value, 0);
    if (Math.abs(total - 100) > 1e-6) fail(`${name}.props.segments values must sum to 100`);
  }
  if (shot.component_id === 'Bits-ChatConversation' && shot.props.semantics === 'quotation') {
    if (!shot.props.source_ref) fail(`${name}.props.source_ref is required for quotation chat semantics`);
    if (!shot.source_label.trim()) fail(`${name}: quotation chat semantics require a source label`);
  }
};

export const createCommunityBindingSpec = (shot) => {
  if (!hasProductionCommunityProps(shot)) return null;
  validateCommunityBindingProps(shot, 'shot');
  const props = shot.props;
  switch (shot.component_id) {
    case 'Rve-StatCounter':
      return {
        component: 'Rve-StatCounter',
        props: {
          value: props.value,
          label: props.label,
          change: props.change,
          period: props.period,
          suffix: props.suffix,
        },
        revealFrame: props.reveal_frame ?? 0,
      };
    case 'Rve-PieChart':
      return {component: 'Rve-PieChart', props: {segments: props.segments, title: props.title}};
    case 'Rve-SplitScreen':
      return {component: 'Rve-SplitScreen', props: {...props}};
    case 'Talkcraft-unit-grid-proportion':
      return {
        component: 'Talkcraft-unit-grid-proportion',
        props: {target: props.target, unit: props.unit, label: props.label, legend: props.legend, accent: shot.accent_color, productionHold: true},
        holdFrame: productionBindings[shot.component_id].hold_frame,
      };
    case 'Talkcraft-source-converge':
      return {
        component: 'Talkcraft-source-converge',
        props: {title: props.title, sources: props.sources, hub: props.hub, caption: props.caption, productionHold: true},
        holdFrame: productionBindings[shot.component_id].hold_frame,
      };
    case 'Bits-ChatConversation':
      return {
        component: 'Bits-ChatConversation',
        props: {messages: props.messages, variant: props.variant, showAvatars: props.showAvatars, stagger: props.stagger},
        badge: props.semantics === 'illustration' ? '机制示意｜非真实对话' : '来源摘录',
      };
    default:
      fail(`shot.component_id does not have a renderer binding`);
  }
};
