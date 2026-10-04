import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const emit = value => process.stdout.write(`${JSON.stringify(value)}\n`);
// 明确限制样片的解帧缓存与线程，控制大帧和并行解码的内存压力。
const offthreadVideoOptions = {offthreadVideoCacheSizeInBytes: 256 * 1024 * 1024, offthreadVideoThreads: 2};

export const parseArgs = argv => {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    const name = argv[index]?.replace(/^--/, '');
    const value = argv[index + 1];
    if (!['config', 'output', 'cover'].includes(name) || !value || !path.isAbsolute(value) || Object.hasOwn(options, name)) throw new Error('Usage: node scripts/render-muse-demo.mjs --config <absolute.json> --output <new-absolute.mp4> --cover <new-absolute.png>');
    options[name] = value;
  }
  for (const [name, extension] of [['config', '.json'], ['output', '.mp4'], ['cover', '.png']]) {
    if (!options[name] || path.extname(options[name]).toLowerCase() !== extension) throw new Error(`--${name} requires an absolute ${extension} path`);
  }
  return options;
};

export const validateConfig = config => {
  if (!config || typeof config !== 'object' || !/^[a-zA-Z0-9_-]{1,80}$/.test(config.job_id)) throw new Error('Invalid demo job_id');
  if (config.width !== 1920 || config.height !== 1080 || ![24, 25, 30, 60].includes(config.fps)) throw new Error('Demo uses 1920×1080 and a supported frame rate');
  if (!Number.isFinite(config.duration_seconds) || config.duration_seconds < 5 || config.duration_seconds > 180) throw new Error('Invalid actual audio duration');
  if (!Array.isArray(config.segments) || !config.segments.length || !Array.isArray(config.captions)) throw new Error('Actual timed segments and captions are required');
  const limit = config.duration_seconds * 1000 + 50;
  const checkTimed = (items, label) => {
    let previousEnd = 0;
    for (const item of items) {
      if (typeof item.text !== 'string' || !item.text.trim() || !Number.isFinite(item.start_ms) || !Number.isFinite(item.end_ms) || item.start_ms < previousEnd || item.end_ms <= item.start_ms || item.end_ms > limit) throw new Error(`Invalid or overlapping ${label} timing`);
      previousEnd = item.end_ms;
    }
  };
  checkTimed(config.segments, 'segment');
  checkTimed(config.captions, 'caption');
  if (new Set(config.segments.map(item => item.id)).size !== config.segments.length || config.segments.some(item => typeof item.id !== 'string' || !item.id)) throw new Error('Segments need unique identifiers');
  return config;
};

const assertNew = async file => {
  try { await fs.lstat(file); } catch (error) { if (error.code === 'ENOENT') return; throw error; }
  throw new Error(`Output already exists: ${file}`);
};

const validateMedia = async config => {
  const publicRoot = await fs.realpath(path.join(root, 'public'));
  const prefix = `videoagents/${config.job_id}/demo/`;
  const sources = [config.audio_src, config.clips?.japan, config.clips?.shopping];
  for (const [index, source] of sources.entries()) {
    if (typeof source !== 'string' || !source.startsWith(prefix) || /[\\?#]/.test(source) || source.split('/').some(part => part === '..' || part === '.')) throw new Error('Demo media must belong to this job under public/videoagents/<job_id>/demo/');
    if (!(index === 0 ? /\.(mp3|wav|m4a)$/i : /\.mp4$/i).test(source)) throw new Error('Demo needs a local audio file and two MP4 clips');
    const expected = path.join(publicRoot, ...source.split('/'));
    const real = await fs.realpath(expected);
    const same = process.platform === 'win32' ? expected.toLowerCase() === real.toLowerCase() : expected === real;
    if (!same || !real.startsWith(`${publicRoot}${path.sep}`)) throw new Error('Demo media cannot escape public via a symlink or junction');
    const stat = await fs.stat(real);
    if (!stat.isFile() || stat.size < 12 || stat.size > 250 * 1024 * 1024) throw new Error('Demo media is missing, empty or too large');
  }
};

export const main = async (argv = process.argv.slice(2)) => {
  const options = parseArgs(argv);
  const stat = await fs.stat(options.config);
  if (!stat.isFile() || stat.size > 1024 * 1024) throw new Error('Config must be a JSON file of at most 1 MiB');
  const config = validateConfig(JSON.parse((await fs.readFile(options.config, 'utf8')).replace(/^\uFEFF/, '')));
  await assertNew(options.output);
  await assertNew(options.cover);
  await validateMedia(config);
  const inputProps = {config};
  let browser;
  try {
    emit({event: 'bundle'});
    const serveUrl = await bundle({entryPoint: path.join(root, 'src', 'demos', 'muse-demo', 'index.tsx'), rootDir: root, publicDir: path.join(root, 'public')});
    browser = await openBrowser('chrome', {logLevel: 'error'});
    const composition = await selectComposition({serveUrl, id: 'MuseDemo', inputProps, puppeteerInstance: browser, logLevel: 'error', ...offthreadVideoOptions});
    await fs.mkdir(path.dirname(options.output), {recursive: true});
    await fs.mkdir(path.dirname(options.cover), {recursive: true});
    emit({event: 'render-settings', concurrency: 2, ...offthreadVideoOptions});
    let lastPercent = -1;
    await renderMedia({serveUrl, composition, inputProps, outputLocation: options.output, overwrite: false, codec: 'h264', audioCodec: 'aac', crf: 18, pixelFormat: 'yuv420p', concurrency: 2, puppeteerInstance: browser, logLevel: 'error', ...offthreadVideoOptions, onProgress: ({progress}) => {
      const percent = Math.floor(progress * 100);
      if (percent >= lastPercent + 5 || percent === 100) { lastPercent = percent; emit({event: 'progress', percent}); }
    }});
    await renderStill({serveUrl, composition, inputProps, output: options.cover, imageFormat: 'png', frame: Math.min(composition.durationInFrames - 1, Math.round(config.fps * 1.5)), puppeteerInstance: browser, logLevel: 'error', ...offthreadVideoOptions});
    emit({event: 'complete', output: options.output, cover: options.cover, duration_seconds: config.duration_seconds});
  } finally { if (browser) await browser.close({silent: true}); }
};

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch(error => { emit({event: 'error', message: error.message}); process.exitCode = 1; });
