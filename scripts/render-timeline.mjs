import {constants} from 'node:fs';
import {execFile} from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {makeCancelSignal, openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {validateTimeline} from '../src/video-production/validation.mjs';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const publicRoot = path.join(projectRoot, 'public');
const execFileAsync = promisify(execFile);
const emit = (message) => process.stdout.write(JSON.stringify(message) + '\n');
const samePath = (a, b) => process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
const inside = (root, candidate) => {
  const relative = path.relative(root, candidate);
  return relative !== '' && !relative.startsWith('..') && !path.isAbsolute(relative);
};

export const parseArgs = (argv) => {
  const options = {};
  const allowed = new Set(['--timeline', '--output', '--mode', '--cover']);
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!allowed.has(key) || !value || value.startsWith('--') || Object.hasOwn(options, key.slice(2))) {
      throw new Error('Usage: node scripts/render-timeline.mjs --timeline <absolute-json> --output <absolute-mp4> --mode preview|final [--cover <absolute-png>]');
    }
    options[key.slice(2)] = value;
  }
  for (const key of ['timeline', 'output']) {
    if (!options[key] || !path.isAbsolute(options[key])) throw new Error(`--${key} requires an absolute path`);
  }
  if (!['preview', 'final'].includes(options.mode)) throw new Error('--mode must be preview or final');
  if (path.extname(options.timeline).toLowerCase() !== '.json') throw new Error('--timeline requires a JSON file');
  if (path.extname(options.output).toLowerCase() !== '.mp4') throw new Error('--output requires an MP4 file');
  if (options.cover && (!path.isAbsolute(options.cover) || path.extname(options.cover).toLowerCase() !== '.png')) {
    throw new Error('--cover requires an absolute PNG file path');
  }
  return options;
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
    ({stdout} = await execFileAsync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration:stream=codec_type,duration,width,height',
      '-of', 'json', file], {maxBuffer: 1024 * 1024}));
  } catch (error) {
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
  const videoShotsBySource = new Map();
  for (const shot of timeline.shots) {
    if (shot.component_id !== 'video' || !shot.asset_src) continue;
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
    if (isVideo) {
      if (!videoShotsBySource.has(source)) throw new Error(`MP4 media is only allowed for video shots: ${source}`);
      const metadata = await videoProbe(actualFile, source);
      videoMetadata[source] = metadata;
      for (const shot of videoShotsBySource.get(source)) {
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
    // Reuse the exact same frozen props for selection, MP4 and cover. Preview
    // changes only output scale; canonical timeline coordinates never change.
    const offthreadVideoOptions = {offthreadVideoCacheSizeInBytes: 256 * 1024 * 1024, offthreadVideoThreads: 2};
    await renderMedia({serveUrl, composition, inputProps, outputLocation: path.join(tempDir, 'video.mp4'),
      codec: 'h264', crf: options.mode === 'preview' ? 26 : 18, pixelFormat: 'yuv420p',
      scale, concurrency: 2, puppeteerInstance: browser, cancelSignal, logLevel: 'error',
      ...offthreadVideoOptions,
      onProgress: (event) => progress(0.15 + event.progress * 0.75)});
    assertRunning();
    if (options.cover) {
      const firstShot = timeline.shots[0];
      const coverFrame = Math.min(firstShot.end_frame - 1, Math.max(firstShot.start_frame, Math.round(timeline.fps * 0.8)));
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
    emit({event: 'complete', output: options.output, cover: options.cover ?? null});
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
