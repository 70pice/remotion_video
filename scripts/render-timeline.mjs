import {constants} from 'node:fs';
import {Buffer} from 'node:buffer';
import {execFile} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {makeCancelSignal, openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {communityComponentIds, validateTimeline} from '../src/video-production/validation.mjs';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const publicRoot = path.join(projectRoot, 'public');
const {structuredClone} = globalThis;
const execFileAsync = promisify(execFile);
const emit = (message) => process.stdout.write(JSON.stringify(message) + '\n');
const samePath = (a, b) => process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
const inside = (root, candidate) => {
  const relative = path.relative(root, candidate);
  return relative !== '' && !relative.startsWith('..') && !path.isAbsolute(relative);
};

// The first ffprobe on PATH may be a stripped build from an IDE that cannot
// even decode plain PCM WAV. Walk the candidates and keep the first one that
// proves it can probe a minimal WAV; VIDEOAGENTS_FFPROBE pins one explicitly.
const silentWav = () => {
  const sampleRate = 16000;
  const frames = 800;
  const data = Buffer.alloc(frames * 2);
  const header = Buffer.alloc(44);
  header.write('RIFF', 0, 'ascii');
  header.writeUInt32LE(36 + data.length, 4);
  header.write('WAVE', 8, 'ascii');
  header.write('fmt ', 12, 'ascii');
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write('data', 36, 'ascii');
  header.writeUInt32LE(data.length, 40);
  return Buffer.concat([header, data]);
};

let resolvedFFprobe;
let resolvedFFmpeg;
const resolveMediaBinary = async (name, overrideEnv, buildArguments, verify) => {
  const resolved = name === 'ffprobe' ? resolvedFFprobe : resolvedFFmpeg;
  if (resolved) return resolved;
  const override = process.env[overrideEnv];
  const directories = (process.env.PATH ?? '').split(path.delimiter).filter(Boolean);
  const candidates = override
    ? [override]
    : directories.flatMap((directory) => [path.join(directory, name), path.join(directory, `${name}.exe`)]);
  const seen = new Set();
  for (const candidate of candidates) {
    let stat;
    try {
      stat = await fs.stat(candidate);
    } catch {
      continue;
    }
    if (!stat.isFile() || !(stat.mode & 0o111)) continue;
    const executable = await fs.realpath(candidate);
    if (seen.has(executable)) continue;
    seen.add(executable);
    const tempFile = path.join(os.tmpdir(), `videoagents-${name}-check-${randomUUID()}.wav`);
    try {
      await fs.writeFile(tempFile, silentWav());
      const {stdout} = await execFileAsync(executable, buildArguments(tempFile), {maxBuffer: 1024 * 1024});
      if (verify(stdout)) {
        if (name === 'ffprobe') resolvedFFprobe = executable;
        else resolvedFFmpeg = executable;
        return executable;
      }
    } catch {
      // Candidate cannot decode a plain WAV; try the next one.
    } finally {
      await fs.rm(tempFile, {force: true});
    }
  }
  throw new Error(override
    ? `${overrideEnv} (${override}) cannot decode a standard WAV; install a full ${name} build`
    : `No ${name} on PATH can decode a standard WAV. Install ffmpeg (macOS: brew install ffmpeg) `
      + `or set ${overrideEnv} to a full build; bundled IDE builds are not sufficient.`);
};

export const ffprobeExecutable = () => resolveMediaBinary(
  'ffprobe', 'VIDEOAGENTS_FFPROBE',
  (tempFile) => ['-v', 'error', '-show_streams', '-of', 'json', tempFile],
  (stdout) => JSON.parse(stdout).streams?.some((item) => item.codec_type === 'audio'));

export const ffmpegExecutable = () => resolveMediaBinary(
  'ffmpeg', 'VIDEOAGENTS_FFMPEG',
  (tempFile) => ['-v', 'error', '-i', tempFile, '-f', 'null', '-'],
  () => true);

export const parseArgs = (argv) => {
  const options = {};
  const allowed = new Set(['--timeline', '--output', '--mode', '--cover', '--start-frame', '--end-frame', '--review-frames']);
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!allowed.has(key) || !value || value.startsWith('--') || Object.hasOwn(options, key.slice(2))) {
      throw new Error('Usage: node scripts/render-timeline.mjs --timeline <absolute-json> --output <absolute-mp4-or-review-json> --mode preview|final|shot-review [--cover <absolute-png>] [--start-frame <frame> --end-frame <exclusive-frame>] [--review-frames <absolute-json>]');
    }
    options[key.slice(2)] = value;
  }
  for (const key of ['timeline', 'output']) {
    if (!options[key] || !path.isAbsolute(options[key])) throw new Error(`--${key} requires an absolute path`);
  }
  if (!['preview', 'final', 'shot-review'].includes(options.mode)) throw new Error('--mode must be preview, final or shot-review');
  if (path.extname(options.timeline).toLowerCase() !== '.json') throw new Error('--timeline requires a JSON file');
  if (options.mode === 'shot-review') {
    if (path.extname(options.output).toLowerCase() !== '.json') throw new Error('shot-review --output requires a JSON manifest');
    if (!options['review-frames'] || !path.isAbsolute(options['review-frames'])) throw new Error('--review-frames requires an absolute JSON request');
    if (path.extname(options['review-frames']).toLowerCase() !== '.json') throw new Error('--review-frames requires a JSON request');
    if (options.cover) throw new Error('shot-review does not accept --cover');
    if (options['start-frame'] !== undefined || options['end-frame'] !== undefined) throw new Error('shot-review uses each requested frame, not a frame range');
  } else {
    if (options['review-frames']) throw new Error('--review-frames is only accepted for shot-review');
    if (path.extname(options.output).toLowerCase() !== '.mp4') throw new Error('--output requires an MP4 file');
  }
  if (options.cover && (!path.isAbsolute(options.cover) || path.extname(options.cover).toLowerCase() !== '.png')) {
    throw new Error('--cover requires an absolute PNG file path');
  }
  const hasStart = options['start-frame'] !== undefined;
  const hasEnd = options['end-frame'] !== undefined;
  if (hasStart !== hasEnd) throw new Error('--start-frame and --end-frame must be provided together');
  if (options.mode === 'final' && hasStart) throw new Error('final render does not accept --start-frame or --end-frame');
  if (hasStart) {
    for (const key of ['start-frame', 'end-frame']) {
      if (!/^(0|[1-9]\d*)$/.test(options[key])) throw new Error(`--${key} must be a nonnegative integer frame`);
      options[key] = Number(options[key]);
      if (!Number.isSafeInteger(options[key])) throw new Error(`--${key} must be a safe integer frame`);
    }
    if (options['end-frame'] <= options['start-frame']) throw new Error('--end-frame must be greater than --start-frame');
    options.frameRange = {startFrame: options['start-frame'], endFrame: options['end-frame']};
  }
  return options;
};

export const validateShotReviewRequest = (timeline, request) => {
  if (!Array.isArray(request) || request.length !== timeline.shots.length) {
    throw new Error('Shot review request must cover every timeline shot exactly once');
  }
  for (const [index, item] of request.entries()) {
    const shot = timeline.shots[index];
    if (!item || typeof item !== 'object' || Array.isArray(item)
        || Object.keys(item).length !== 2 || !Object.hasOwn(item, 'shot_id') || !Object.hasOwn(item, 'frame')
        || item.shot_id !== shot.shot_id) {
      throw new Error('Shot review request must preserve timeline shot IDs and order');
    }
    if (!Number.isSafeInteger(item.frame) || item.frame < shot.start_frame || item.frame >= shot.end_frame) {
      throw new Error(`Shot review frame must be inside its shot: ${shot.shot_id}`);
    }
  }
  return request;
};

const reviewImagePath = (output, index) => path.join(path.dirname(output), `shot-${String(index + 1).padStart(3, '0')}.png`);

// Render from the existing frozen composition. Only the requested absolute
// frame varies: audio, captions, shot-local clocks and component choices stay
// identical to the complete film. Publish the manifest after every PNG exists.
export const renderShotReviewImages = async ({timeline, request, output, tempDir, renderFrame, progress, assertRunning}) => {
  validateShotReviewRequest(timeline, request);
  await assertNewOutput(output);
  for (const index of request.keys()) await assertNewOutput(reviewImagePath(output, index));
  const imageRoot = path.join(tempDir, 'shot-review');
  await fs.mkdir(imageRoot, {recursive: true});
  const images = [];
  for (const [index, item] of request.entries()) {
    assertRunning();
    const staged = path.join(imageRoot, `shot-${String(index + 1).padStart(3, '0')}.png`);
    await renderFrame(item.frame, staged);
    const stat = await fs.stat(staged);
    if (!stat.isFile() || stat.size === 0) throw new Error(`Shot review PNG is missing or empty: ${item.shot_id}`);
    images.push({...item, width: timeline.width, height: timeline.height, path: reviewImagePath(output, index)});
    progress(0.15 + (index + 1) / request.length * 0.75);
  }
  assertRunning();
  await fs.mkdir(path.dirname(output), {recursive: true});
  const pendingManifest = path.join(path.dirname(output), `${path.basename(output)}.pending-${randomUUID()}`);
  const publishedImages = [];
  try {
    for (const [index, image] of images.entries()) {
      assertRunning();
      await fs.copyFile(path.join(imageRoot, `shot-${String(index + 1).padStart(3, '0')}.png`), image.path, constants.COPYFILE_EXCL);
      publishedImages.push(image.path);
    }
    await fs.writeFile(pendingManifest, JSON.stringify(images, null, 2), {encoding: 'utf8', flag: 'wx'});
    assertRunning();
    // Same-directory hard link publishes all JSON bytes atomically and cannot
    // overwrite a manifest created by another invocation in the meantime.
    await fs.link(pendingManifest, output);
    return images;
  } catch (error) {
    for (const file of publishedImages) await fs.unlink(file).catch(() => {});
    throw error;
  } finally {
    await fs.unlink(pendingManifest).catch((error) => { if (error.code !== 'ENOENT') throw error; });
  }
};

export const resolvePreviewFrameRange = (timeline, options) => {
  if (options.mode === 'final') return null;
  const maxFrames = timeline.fps * 30;
  const requested = options.frameRange ?? {startFrame: 0, endFrame: Math.min(timeline.duration_in_frames, maxFrames)};
  if (requested.startFrame < 0 || requested.endFrame <= requested.startFrame) {
    throw new Error('Preview frame range must be a nonempty half-open interval');
  }
  if (requested.endFrame > timeline.duration_in_frames) {
    throw new Error('Preview frame range is outside the timeline duration');
  }
  if (requested.endFrame - requested.startFrame > maxFrames) {
    throw new Error('Preview frame range may not exceed 30 seconds');
  }
  return {
    startFrame: requested.startFrame,
    endFrame: requested.endFrame,
    remotionFrameRange: [requested.startFrame, requested.endFrame - 1],
  };
};

export const selectCoverFrame = (timeline, frameRange) => {
  const firstShot = timeline.shots[0];
  const coverStart = frameRange?.startFrame ?? 0;
  const coverEnd = frameRange?.endFrame ?? timeline.duration_in_frames;
  const preferredFrame = Math.min(firstShot.end_frame - 1, Math.max(firstShot.start_frame, Math.round(timeline.fps * 0.8)));
  return Math.min(coverEnd - 1, Math.max(coverStart, preferredFrame));
};

const assertNewOutput = async (file) => {
  if (!file) return;
  try {
    await fs.lstat(file);
    throw new Error(`Output already exists: ${file}`);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
};

const recognizableMedia = (source, header) => {
  const extension = path.extname(source).toLowerCase();
  if (extension === '.png') return header.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  if (['.jpg', '.jpeg'].includes(extension)) return header[0] === 255 && header[1] === 216 && header[2] === 255;
  if (extension === '.webp') return header.toString('ascii', 0, 4) === 'RIFF' && header.toString('ascii', 8, 12) === 'WEBP';
  if (extension === '.wav') return header.toString('ascii', 0, 4) === 'RIFF' && header.toString('ascii', 8, 12) === 'WAVE';
  if (extension === '.ogg') return header.toString('ascii', 0, 4) === 'OggS';
  if (extension === '.m4a') return header.toString('ascii', 4, 8) === 'ftyp';
  if (extension === '.mp4') return header.toString('ascii', 4, 8) === 'ftyp' && header.toString('ascii', 8, 12) !== 'M4A ';
  if (extension === '.mp3') return header.toString('ascii', 0, 3) === 'ID3' || (header[0] === 255 && (header[1] & 224) === 224);
  if (extension === '.aac') return header[0] === 255 && (header[1] & 246) === 240;
  return false;
};

const videoProbe = async (file, source) => {
  let stdout;
  try {
    ({stdout} = await execFileAsync(await ffprobeExecutable(), ['-v', 'error', '-show_entries', 'format=duration:stream=codec_type,duration,width,height',
      '-of', 'json', file], {maxBuffer: 1024 * 1024}));
  } catch {
    throw new Error(`Video media must contain a video stream readable by ffprobe: ${source}`);
  }
  let info;
  try {
    info = JSON.parse(stdout);
  } catch {
    throw new Error(`Video media probe returned invalid JSON: ${source}`);
  }
  const stream = info.streams?.find((item) => item.codec_type === 'video');
  if (!stream) throw new Error(`Video media must contain a video stream, not audio-only MP4/M4A: ${source}`);
  const duration = Number(stream.duration ?? info.format?.duration);
  if (!Number.isFinite(duration) || duration <= 0) throw new Error(`Video media duration is unavailable: ${source}`);
  const width = Number(stream.width);
  const height = Number(stream.height);
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width <= 0 || height <= 0) {
    throw new Error(`Video media dimensions are unavailable: ${source}`);
  }
  return {duration, width, height};
};

export const validateLocalInputs = async (timeline) => {
  validateTimeline(timeline);
  const sources = [...new Set([timeline.audio_src, ...timeline.shots.map((shot) => shot.asset_src)].filter(Boolean))];
  if (!sources.length) return {files: [], videoMetadata: {}};
  // Same acceptance as validateTimeline: the `video` adapter and community
  // presets (whose media slots render MP4 via OffthreadVideo) may consume
  // video; semantic components take images only.
  const communitySet = new Set(communityComponentIds);
  const consumesVideo = (componentId) => componentId === 'video' || communitySet.has(componentId);
  const videoShotsBySource = new Map();
  for (const shot of timeline.shots) {
    if (!consumesVideo(shot.component_id) || !shot.asset_src || !/\.mp4$/i.test(shot.asset_src)) continue;
    const items = videoShotsBySource.get(shot.asset_src) ?? [];
    items.push(shot);
    videoShotsBySource.set(shot.asset_src, items);
  }
  const canonicalPublicRoot = await fs.realpath(publicRoot);
  const expectedJobRoot = path.join(canonicalPublicRoot, 'videoagents', timeline.job_id);
  const canonicalJobRoot = await fs.realpath(expectedJobRoot);
  if (!samePath(canonicalJobRoot, expectedJobRoot)) throw new Error('Job media directory must not be a symlink or junction');
  const files = [];
  const videoMetadata = {};
  for (const source of sources) {
    const expectedFile = path.join(canonicalPublicRoot, ...source.split('/'));
    const actualFile = await fs.realpath(expectedFile);
    if (!inside(canonicalJobRoot, actualFile) || !samePath(actualFile, expectedFile)) {
      throw new Error('Media may not escape its own job directory via symlinks, junctions or traversal');
    }
    const stat = await fs.stat(actualFile);
    const isImage = /\.(png|jpe?g|webp)$/i.test(source);
    const isVideo = /\.mp4$/i.test(source);
    const maxBytes = (isImage ? 50 : 250) * 1024 * 1024;
    if (!stat.isFile() || stat.size < 12 || stat.size > maxBytes) throw new Error(`Media is empty, too large or not a regular file: ${source}`);
    const handle = await fs.open(actualFile, 'r');
    try {
      const buffer = Buffer.alloc(32);
      const {bytesRead} = await handle.read(buffer, 0, buffer.length, 0);
      if (!recognizableMedia(source, buffer.subarray(0, bytesRead))) throw new Error(`Media content does not match its allowed format: ${source}`);
    } finally {
      await handle.close();
    }
    const focusShots = timeline.shots.filter((shot) => shot.asset_src === source && shot.props.focus_source_size);
    if (isImage && focusShots.length) {
      const {stdout} = await execFileAsync(await ffprobeExecutable(), ['-v', 'error', '-show_entries', 'stream=width,height', '-of', 'json', actualFile]);
      const dimensions = JSON.parse(stdout).streams?.[0];
      for (const shot of focusShots) {
        const size = shot.props.focus_source_size;
        if (!dimensions || size.width !== dimensions.width || size.height !== dimensions.height) {
          throw new Error(`Focus source dimensions must match measured media: ${source}`);
        }
      }
    }
    if (isVideo) {
      if (!videoShotsBySource.has(source)) throw new Error(`MP4 media requires a supported video component: ${source}`);
      const metadata = await videoProbe(actualFile, source);
      videoMetadata[source] = metadata;
      for (const shot of videoShotsBySource.get(source)) {
        const tutorialSize = shot.props.tutorial_source_size;
        if (tutorialSize && (tutorialSize.width !== metadata.width || tutorialSize.height !== metadata.height)) {
          throw new Error(`Tutorial source dimensions must match measured media: ${source}`);
        }
        const focusSize = shot.props.focus_source_size;
        if (focusSize && (focusSize.width !== metadata.width || focusSize.height !== metadata.height)) {
          throw new Error(`Focus source dimensions must match measured media: ${source}`);
        }
        const start = shot.props.start_seconds ?? 0;
        const end = shot.props.end_seconds ?? metadata.duration;
        const shotSeconds = (shot.end_frame - shot.start_frame) / timeline.fps;
        if (start >= metadata.duration || end > metadata.duration + 0.001) {
          throw new Error(`Video trim range is outside the source duration: ${source}`);
        }
        if (end - start + 0.001 < shotSeconds) {
          throw new Error(`Video trim range is too short for the shot duration: ${source}`);
        }
      }
    }
    files.push({source, file: actualFile});
  }
  return {files, videoMetadata};
};

export const snapshotBuiltInAssets = async (snapshotRoot) => {
  // 注册组件时也会加载内置字体；只冻结任务图片和音频会让字体请求失败。
  await fs.cp(path.join(publicRoot, 'community'), path.join(snapshotRoot, 'community'), {
    recursive: true, force: false, errorOnExist: true,
    filter: async (source) => {
      if ((await fs.lstat(source)).isSymbolicLink()) {
        throw new Error('Built-in media must not be a symlink or junction');
      }
      return true;
    },
  });
};

const freezeDeep = (value) => {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freezeDeep);
    Object.freeze(value);
  }
  return value;
};

export const outputScale = (timeline, mode) => {
  if (mode === 'shot-review') return 1;
  // H.264 yuv420p also requires the *scaled* dimensions to be even. Keep
  // canonical dimensions for unusual even sizes that would become odd at 1/2.
  return mode === 'preview' && timeline.width % 4 === 0 && timeline.height % 4 === 0 ? 0.5 : 1;
};

export const main = async (argv = process.argv.slice(2)) => {
  const options = parseArgs(argv);
  const inputStat = await fs.stat(options.timeline);
  if (!inputStat.isFile() || inputStat.size > 1024 * 1024) throw new Error('Timeline must be a local JSON file of at most 1 MiB');
  const text = await fs.readFile(options.timeline, 'utf8');
  const timeline = validateTimeline(JSON.parse(text.replace(/^\uFEFF/, '')));
  await assertNewOutput(options.output);
  await assertNewOutput(options.cover);
  let reviewRequest;
  if (options.mode === 'shot-review') {
    const requestStat = await fs.stat(options['review-frames']);
    if (!requestStat.isFile() || requestStat.size > 1024 * 1024) throw new Error('Shot review request must be a local JSON file of at most 1 MiB');
    reviewRequest = validateShotReviewRequest(timeline, JSON.parse((await fs.readFile(options['review-frames'], 'utf8')).replace(/^\uFEFF/, '')));
    for (const index of reviewRequest.keys()) await assertNewOutput(reviewImagePath(options.output, index));
  }
  const media = await validateLocalInputs(timeline);
  const inputProps = freezeDeep({timeline: structuredClone(timeline), videoMetadata: structuredClone(media.videoMetadata)});
  const canonicalTempRoot = await fs.realpath(os.tmpdir());
  const tempDir = await fs.mkdtemp(path.join(canonicalTempRoot, 'videoagents-render-'));
  let browser;
  let interrupted = false;
  const {cancel, cancelSignal} = makeCancelSignal();
  const stop = () => { interrupted = true; cancel(); };
  const assertRunning = () => { if (interrupted) throw new Error('Render cancelled'); };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
  let lastProgress = -1;
  const progress = (value) => {
    const rounded = Math.round(Math.max(0, Math.min(1, value)) * 1000) / 1000;
    if (rounded >= lastProgress + 0.005 || rounded === 1) {
      lastProgress = rounded;
      emit({event: 'progress', progress: rounded});
    }
  };
  try {
    progress(0);
    const snapshotRoot = path.join(tempDir, 'public');
    await fs.mkdir(snapshotRoot, {recursive: true});
    await snapshotBuiltInAssets(snapshotRoot);
    for (const {source, file} of media.files) {
      const target = path.join(snapshotRoot, ...source.split('/'));
      await fs.mkdir(path.dirname(target), {recursive: true});
      await fs.copyFile(file, target, constants.COPYFILE_EXCL);
    }
    assertRunning();
    const serveUrl = await bundle({entryPoint: path.join(projectRoot, 'src', 'video-production', 'index.tsx'),
      rootDir: projectRoot, publicDir: snapshotRoot, outDir: path.join(tempDir, 'bundle'),
      onProgress: (value) => progress(0.02 + value / 100 * 0.13)});
    assertRunning();
    browser = await openBrowser('chrome', {logLevel: 'error'});
    const composition = await selectComposition({serveUrl, id: 'VideoFromTimeline', inputProps,
      puppeteerInstance: browser, logLevel: 'error'});
    assertRunning();
    const scale = outputScale(timeline, options.mode);
    const frameRange = options.mode === 'shot-review' ? null : resolvePreviewFrameRange(timeline, options);
    // Reuse the exact same frozen props for selection, MP4 and cover. Preview
    // changes only output scale and renderMedia's source frame range; canonical
    // timeline coordinates, audio time and shot-local animation never change.
    const offthreadVideoOptions = {offthreadVideoCacheSizeInBytes: 256 * 1024 * 1024, offthreadVideoThreads: 2};
    if (options.mode === 'shot-review') {
      const images = await renderShotReviewImages({timeline, request: reviewRequest, output: options.output, tempDir,
        progress, assertRunning,
        renderFrame: (frame, output) => renderStill({serveUrl, composition, inputProps, output, imageFormat: 'png',
          frame, scale: 1, puppeteerInstance: browser, cancelSignal, logLevel: 'error', ...offthreadVideoOptions})});
      progress(1);
      emit({event: 'complete', output: options.output, images});
      return;
    }
    await renderMedia({serveUrl, composition, inputProps, outputLocation: path.join(tempDir, 'video.mp4'),
      codec: 'h264', crf: options.mode === 'preview' ? 26 : 18, pixelFormat: 'yuv420p',
      scale, concurrency: 2, puppeteerInstance: browser, cancelSignal, logLevel: 'error',
      ...(frameRange ? {frameRange: frameRange.remotionFrameRange} : {}),
      ...offthreadVideoOptions,
      onProgress: (event) => progress(0.15 + event.progress * 0.75)});
    assertRunning();
    if (options.cover) {
      const coverFrame = selectCoverFrame(timeline, frameRange);
      await renderStill({serveUrl, composition, inputProps, output: path.join(tempDir, 'cover.png'),
        imageFormat: 'png', frame: coverFrame, scale, puppeteerInstance: browser, cancelSignal, logLevel: 'error',
        ...offthreadVideoOptions});
    }
    assertRunning();
    await fs.mkdir(path.dirname(options.output), {recursive: true});
    await fs.copyFile(path.join(tempDir, 'video.mp4'), options.output, constants.COPYFILE_EXCL);
    if (options.cover) {
      await fs.mkdir(path.dirname(options.cover), {recursive: true});
      await fs.copyFile(path.join(tempDir, 'cover.png'), options.cover, constants.COPYFILE_EXCL);
    }
    progress(1);
    emit({event: 'complete', output: options.output, cover: options.cover ?? null,
      frame_range: frameRange ? {start_frame: frameRange.startFrame, end_frame: frameRange.endFrame} : null});
  } finally {
    process.off('SIGINT', stop);
    process.off('SIGTERM', stop);
    if (browser) await browser.close({silent: true});
    // Only delete the unique temporary directory created in this invocation.
    const actualTempDir = await fs.realpath(tempDir);
    if (samePath(path.dirname(actualTempDir), canonicalTempRoot) && path.basename(actualTempDir).startsWith('videoagents-render-')) {
      await fs.rm(actualTempDir, {recursive: true, force: true});
    }
  }
};

if (process.argv[1] && samePath(path.resolve(process.argv[1]), fileURLToPath(import.meta.url))) {
  main().catch((error) => {
    emit({event: 'error', message: String(error.message ?? error).slice(0, 4000)});
    process.exitCode = String(error.message).includes('cancelled') ? 130 : 1;
  });
}
