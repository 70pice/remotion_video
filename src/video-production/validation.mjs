// Shared by the Remotion browser bundle and the Node renderer. This module has
// no Node dependencies so validation is identical at both entry points.
export const productionComponentIds = Object.freeze([
  'title', 'keyword', 'evidence', 'image_focus', 'comparison', 'data', 'steps', 'conclusion',
]);

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
  const props = object(shot.props, `${name}.props`);
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
      keys(props, ['highlight'], `${name}.props`);
      if (!shot.asset_src || !shot.source_label.trim()) fail(`${name}: evidence requires an image and a source label`);
      if (props.highlight !== undefined) {
        const highlight = object(props.highlight, `${name}.props.highlight`);
        keys(highlight, ['x', 'y', 'width', 'height'], `${name}.props.highlight`);
        for (const field of ['x', 'y', 'width', 'height']) fraction(highlight[field], `${name}.props.highlight.${field}`);
        if (highlight.width === 0 || highlight.height === 0 || highlight.x + highlight.width > 1 || highlight.y + highlight.height > 1) {
          fail(`${name}.props.highlight must be a nonempty rectangle inside the image`);
        }
      }
      break;
    }
    case 'image_focus':
      keys(props, ['focal_x', 'focal_y'], `${name}.props`);
      if (!shot.asset_src) fail(`${name}: image_focus requires an image`);
      for (const field of ['focal_x', 'focal_y']) if (props[field] !== undefined) fraction(props[field], `${name}.props.${field}`);
      break;
    case 'comparison':
      keys(props, ['left_title', 'left_body', 'right_title', 'right_body'], `${name}.props`);
      for (const field of ['left_title', 'right_title']) text(props[field], `${name}.props.${field}`, 48, true);
      for (const field of ['left_body', 'right_body']) text(props[field], `${name}.props.${field}`, 160, true);
      break;
    case 'data':
      keys(props, ['items'], `${name}.props`);
      if (!Array.isArray(props.items) || props.items.length < 1 || props.items.length > 4) fail(`${name}.props.items requires 1 to 4 supplied data items`);
      props.items.forEach((raw, index) => {
        const item = object(raw, `${name}.props.items[${index}]`);
        keys(item, ['label', 'value', 'detail'], `${name}.props.items[${index}]`);
        text(item.label, `${name}.props.items[${index}].label`, 48, true);
        text(item.value, `${name}.props.items[${index}].value`, 40, true);
        optionalText(item.detail, `${name}.props.items[${index}].detail`, 64);
      });
      break;
    case 'steps':
      keys(props, ['items'], `${name}.props`);
      if (!Array.isArray(props.items) || props.items.length < 1 || props.items.length > 4) fail(`${name}.props.items requires 1 to 4 supplied steps`);
      props.items.forEach((raw, index) => {
        const item = object(raw, `${name}.props.items[${index}]`);
        keys(item, ['title', 'body'], `${name}.props.items[${index}]`);
        text(item.title, `${name}.props.items[${index}].title`, 48, true);
        optionalText(item.body, `${name}.props.items[${index}].body`, 96);
      });
      break;
    case 'conclusion':
      keys(props, ['call_to_action'], `${name}.props`);
      optionalText(props.call_to_action, `${name}.props.call_to_action`, 72);
      break;
    default:
      fail(`${name}.component_id is not a production adapter`);
  }
};

export const validateTimeline = (input) => {
  const timeline = object(input, 'timeline');
  keys(timeline, ['schema_version', 'job_id', 'revision', 'width', 'height', 'fps', 'duration_in_frames', 'audio_src', 'shots', 'captions'], 'timeline');
  if (timeline.schema_version !== '1') fail('schema_version must be "1"');
  if (typeof timeline.job_id !== 'string' || !/^[a-zA-Z0-9_-]{1,100}$/.test(timeline.job_id)) fail('job_id must be a safe task identifier');
  integer(timeline.revision, 'revision', 1, Number.MAX_SAFE_INTEGER);
  integer(timeline.width, 'width', 240, 3840);
  integer(timeline.height, 'height', 240, 3840);
  if (timeline.width % 2 || timeline.height % 2) fail('width and height must be even for H.264');
  integer(timeline.fps, 'fps', 1, 60);
  integer(timeline.duration_in_frames, 'duration_in_frames', 1, timeline.fps * 3600);
  validateMediaSource(timeline.audio_src, timeline.job_id, 'audio_src');
  if (timeline.audio_src && !/\.(wav|mp3|m4a|aac|ogg)$/i.test(timeline.audio_src)) fail('audio_src has an unsupported audio extension');
  if (!Array.isArray(timeline.shots) || timeline.shots.length < 1 || timeline.shots.length > 3000) fail('shots must contain 1 to 3000 shots');
  let expectedStart = 0;
  const identifiers = new Set();
  timeline.shots.forEach((raw, index) => {
    const name = `shots[${index}]`;
    const shot = object(raw, name);
    keys(shot, ['shot_id', 'start_frame', 'end_frame', 'component_id', 'title', 'body', 'asset_src', 'source_label', 'accent_color', 'props'], name);
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
    if (typeof shot.accent_color !== 'string' || !/^#[a-fA-F0-9]{6}$/.test(shot.accent_color)) fail(`${name}.accent_color must be a six-digit hex color`);
    validateMediaSource(shot.asset_src, timeline.job_id, `${name}.asset_src`);
    if (shot.asset_src && !/\.(png|jpe?g|webp)$/i.test(shot.asset_src)) fail(`${name}.asset_src requires a PNG, JPEG or WebP image`);
    validateProps(shot, name);
  });
  if (expectedStart !== timeline.duration_in_frames) fail('shots must end at duration_in_frames');
  if (!Array.isArray(timeline.captions) || timeline.captions.length > 20000) fail('captions must be an array of at most 20000 segments');
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
