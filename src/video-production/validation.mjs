// Shared by the Remotion browser bundle and the Node renderer. This module has
// no Node dependencies so validation is identical at both entry points.
import componentManifest from '../../videoagents/component-manifest.json' with {type: 'json'};
import {
  hasBoundCommunityComponent,
  validateCommunityBindingProps,
} from './communityBindingValidation.mjs';

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
const finiteNumber = (value, name, minimum = -Infinity, maximum = Infinity) => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < minimum || value > maximum) {
    fail(`${name} must be a finite number from ${minimum} to ${maximum}`);
  }
};
const httpUrl = (value, name) => {
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
  const validateCue = (cue, cueName) => integer(cue, cueName, 0, shot.end_frame - shot.start_frame - 15);
  const validateFocusCues = (cues) => {
    if (!Array.isArray(cues) || cues.length < 1 || cues.length > 8) fail(`${name}.props.focus_cues requires 1 to 8 focus cues`);
    let previous = -1;
    cues.forEach((raw, index) => {
      const cue = object(raw, `${name}.props.focus_cues[${index}]`);
      keys(cue, ['frame', 'region', 'label'], `${name}.props.focus_cues[${index}]`);
      validateCue(cue.frame, `${name}.props.focus_cues[${index}].frame`);
      if (index === 0 && cue.frame !== 0) fail(`${name}.props.focus_cues[0].frame must be 0`);
      if (cue.frame <= previous) fail(`${name}.props.focus_cues frames must be strictly increasing`);
      previous = cue.frame;
      if (cue.region !== undefined) normalizedRect(cue.region, `${name}.props.focus_cues[${index}].region`, 'image');
      optionalText(cue.label, `${name}.props.focus_cues[${index}].label`, 24);
    });
  };
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
    if (hasBoundCommunityComponent(shot.component_id) && Object.keys(props).length > 0) {
      validateCommunityBindingProps(shot, name);
      return;
    }
    keys(props, [], `${name}.props`);
    if (shot.asset_src) fail(`${name}: preset components do not accept asset_src`);
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
      keys(props, ['highlight', 'focus_cues'], `${name}.props`);
      if (!shot.asset_src || !shot.source_label.trim()) fail(`${name}: evidence requires an image and a source label`);
      if (props.focus_cues !== undefined) {
        if (props.highlight !== undefined) fail(`${name}.props.focus_cues cannot be mixed with highlight`);
        validateFocusCues(props.focus_cues);
      }
      if (props.highlight !== undefined) {
        normalizedRect(props.highlight, `${name}.props.highlight`, 'image');
      }
      break;
    }
    case 'image_focus':
      keys(props, ['focal_x', 'focal_y', 'crop', 'focus_cues'], `${name}.props`);
      if (!shot.asset_src) fail(`${name}: image_focus requires an image`);
      if (props.focus_cues !== undefined) {
        if (props.focal_x !== undefined || props.focal_y !== undefined || props.crop !== undefined) {
          fail(`${name}.props.focus_cues cannot be mixed with focal_x, focal_y or crop`);
        }
        validateFocusCues(props.focus_cues);
      }
      for (const field of ['focal_x', 'focal_y']) if (props[field] !== undefined) fraction(props[field], `${name}.props.${field}`);
      if (props.crop !== undefined) {
        normalizedRect(props.crop, `${name}.props.crop`, 'image');
      }
      break;
    case 'video': {
      keys(props, ['start_seconds', 'end_seconds', 'fit', 'crop'], `${name}.props`);
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
      keys(props, ['items', 'visualization', 'scale_max', 'unit', 'reference_value', 'source_ref'], `${name}.props`);
      if (props.visualization !== undefined && !['cards', 'bars', 'donuts'].includes(props.visualization)) {
        fail(`${name}.props.visualization must be cards, bars or donuts`);
      }
      {
        const visualization = props.visualization ?? 'cards';
        const chart = ['bars', 'donuts'].includes(visualization);
        if (chart && !shot.source_label.trim()) fail(`${name}: data charts require a source label`);
        if (!chart && props.source_ref !== undefined) fail(`${name}.props.source_ref is only supported for bars or donuts`);
        if (visualization === 'cards') {
          for (const field of ['scale_max', 'unit', 'reference_value']) {
            if (props[field] !== undefined) fail(`${name}.props.${field} is only supported for bars or donuts`);
          }
        }
        if (!Array.isArray(props.items) || props.items.length < 1 || props.items.length > (visualization === 'donuts' ? 2 : 4)) {
          fail(`${name}.props.items requires 1 to 4 supplied data items; donuts accepts at most 2`);
        }
        if (chart) httpUrl(props.source_ref, `${name}.props.source_ref`);
        if (visualization === 'bars') {
          finiteNumber(props.scale_max, `${name}.props.scale_max`, Number.MIN_VALUE);
          text(props.unit, `${name}.props.unit`, 24, true);
          if (props.reference_value !== undefined) finiteNumber(props.reference_value, `${name}.props.reference_value`, 0, props.scale_max);
        }
        if (visualization === 'donuts') {
          if (props.unit !== '%') fail(`${name}.props.unit must be % for donuts`);
          if (props.scale_max !== undefined || props.reference_value !== undefined) {
            fail(`${name}.props.scale_max and reference_value are unsupported for donuts`);
          }
        }
      props.items.forEach((raw, index) => {
        const item = object(raw, `${name}.props.items[${index}]`);
        keys(item, chart ? ['label', 'value', 'detail', 'reveal_frame', 'numeric_value'] : ['label', 'value', 'detail', 'reveal_frame'], `${name}.props.items[${index}]`);
        text(item.label, `${name}.props.items[${index}].label`, 48, true);
        text(item.value, `${name}.props.items[${index}].value`, 40, true);
        optionalText(item.detail, `${name}.props.items[${index}].detail`, 64);
        if (chart) {
          finiteNumber(item.numeric_value, `${name}.props.items[${index}].numeric_value`, 0, visualization === 'donuts' ? 100 : props.scale_max);
        }
      });
      }
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
    if (shot.asset_src && (shot.component_id === 'video' ? !/\.mp4$/i.test(shot.asset_src) : !/\.(png|jpe?g|webp)$/i.test(shot.asset_src))) {
      fail(`${name}.asset_src requires ${shot.component_id === 'video' ? 'an MP4 video' : 'a PNG, JPEG or WebP image'}`);
    }
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
