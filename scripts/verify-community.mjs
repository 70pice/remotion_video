import {bundle} from '@remotion/bundler';
import {getCompositions, openBrowser, renderStill} from '@remotion/renderer';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const expectedPresetCount = 187;
const expectedRegisteredCount = expectedPresetCount * 2;
const packageInfo = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'));
const outputDir = path.join(root, 'out', 'components');
await mkdir(outputDir, {recursive: true});
const libraries = ['snapcn', 'rve', 'remocn', 'remotion-ui', 'bits', 'rendercomp', 'video-talkcraft'];
const catalogues = await Promise.all(libraries.map(async (library) =>
  JSON.parse(await readFile(path.join(root, 'src/components/community', `catalog-${library}.json`), 'utf8'))));
const expected = catalogues.flat();
if (expected.length !== expectedPresetCount || new Set(expected.map((c) => c.compositionId)).size !== expectedPresetCount) {
  throw new Error(`Expected ${expectedPresetCount} unique source compositions.`);
}
const manifest = JSON.parse(await readFile(path.join(root, 'licenses/community/video-talkcraft/source-manifest.json'), 'utf8'));
const normalizeLineEndings = (bytes) => Buffer.from(bytes.toString('utf8').replace(/\r\n/g, '\n'));
let locallyAdapted = 0;
let crlfNormalized = 0;
for (const file of manifest.files) {
  const bytes = await readFile(path.join(root, file.localPath));
  if (file.local_sha256) {
    // Same contract as check-component-paths.mjs: locally adapted files are
    // verified against their adaptation hash, not the upstream original.
    if (file.local_sha256_normalization !== undefined && file.local_sha256_normalization !== 'lf') {
      throw new Error(`${file.slug}: unsupported local hash normalization`);
    }
    const hash = createHash('sha256').update(file.local_sha256_normalization === 'lf' ? normalizeLineEndings(bytes) : bytes).digest('hex');
    if (hash !== file.local_sha256) throw new Error(`Locally adapted source modified: ${file.slug}`);
    locallyAdapted++;
    continue;
  }
  const hash = createHash('sha256').update(normalizeLineEndings(bytes)).digest('hex');
  if (hash !== file.sha256) throw new Error(`Original source modified: ${file.slug}`);
  if (createHash('sha256').update(bytes).digest('hex') !== file.sha256) crlfNormalized++;
}
console.log(`108 Talkcraft sources verified (${locallyAdapted} locally adapted, ${crlfNormalized} CRLF-normalized). `
  + `Bundling ${expectedPresetCount} original and ${expectedPresetCount} native portrait previews...`);
const registrationSource = await readFile(path.join(root, 'src/components/community/CommunityRoot.tsx'), 'utf8');
if (/VerticalStage|sourceWidth|sourceHeight/.test(registrationSource)) {
  throw new Error('Portrait registrations must use native layouts, not the old landscape wrapper.');
}
const serveUrl = await bundle({entryPoint: path.join(root, 'src', 'community.ts')});
const browser = await openBrowser('chrome');
const results = [];
const portraitResults = [];
try {
  const compositions = await getCompositions(serveUrl, {puppeteerInstance: browser});
  const registered = new Map(compositions.map((c) => [c.id, c]));
  if (registered.size !== expectedRegisteredCount ||
    expected.some((c) => !registered.has(c.compositionId) || !registered.has(`Vertical-${c.compositionId}`))) {
    throw new Error(`Registered original/native portrait compositions differ from the ${expectedPresetCount}-component catalogue.`);
  }
  const selected = process.env.COMPONENT_FILTER ? expected.filter((c) => c.compositionId.includes(process.env.COMPONENT_FILTER)) : expected;
  if (!selected.length) throw new Error('Component filter selected no compositions.');
  const run = async (composition, frames) => {
    const hashes = [], errors = [];
    for (const frame of frames) {
      const output = path.join(outputDir, `${composition.id}-${frame}.png`);
      await renderStill({serveUrl, composition, frame, output, scale: 1, puppeteerInstance: browser,
        onBrowserLog: (log) => {if (log.type === 'error') errors.push(log.text);},
      });
      hashes.push(createHash('sha256').update(await readFile(output)).digest('hex'));
    }
    if (errors.length) throw new Error(`${composition.id}: ${errors.join('\n')}`);
    return {id: composition.id, width: composition.width, height: composition.height, fps: composition.fps,
      durationInFrames: composition.durationInFrames, frames, images: frames.map((f) => `${composition.id}-${f}.png`), frameHashes: hashes, status: 'passed'};
  };
  for (const item of selected) {
    const composition = registered.get(item.compositionId);
    const middle = Math.floor(composition.durationInFrames / 2);
    const frames = [...new Set([0, middle, composition.durationInFrames - 1])];
    const result = await run(composition, frames);
    if (new Set(result.frameHashes).size < 2) throw new Error(`${composition.id} did not change across sampled frames.`);
    results.push(result);
    const portrait = registered.get(`Vertical-${item.compositionId}`);
    if (!portrait) throw new Error(`Missing native portrait preview: Vertical-${item.compositionId}`);
    if (portrait.width !== 1080 || portrait.height !== 1920 || portrait.fps !== 30) throw new Error(`Invalid portrait spec: ${portrait.id}`);
    const portraitMiddle = Math.floor(portrait.durationInFrames / 2);
    const portraitFrames = [...new Set([0, portraitMiddle, portrait.durationInFrames - 1])];
    const portraitResult = await run(portrait, portraitFrames);
    if (new Set(portraitResult.frameHashes).size < 2) throw new Error(`${portrait.id} did not change across sampled frames.`);
    portraitResults.push({...portraitResult, layout: 'native-portrait', previewImage: portraitResult.images[portraitResult.frames.indexOf(portraitMiddle)]});
    await writeFile(path.join(outputDir, 'verification-progress.json'), JSON.stringify({results, portraitResults}, null, 2));
    console.log(`[${results.length}/${selected.length}] ${composition.id}: original 3 frames + native portrait 3 frames passed`);
  }
} finally {await browser.close({silent: true});}
if (process.env.COMPONENT_FILTER) {
  await writeFile(path.join(outputDir, 'verification-focused.json'), JSON.stringify({results, portraitResults}, null, 2));
} else {
  await writeFile(path.join(outputDir, 'verification.json'), JSON.stringify({checkedAt: new Date().toISOString(),
    runtimeVersion: packageInfo.dependencies.remotion, count: results.length, portraitCount: portraitResults.length,
    registeredCount: expectedRegisteredCount, preservedSourceCount: manifest.files.length,
    results, portraitResults,
    scope: `${expectedPresetCount} original and ${expectedPresetCount} native portrait previews at start/middle/end, full resolution. Render checks do not prove arbitrary text/props layouts or pixel-equivalence to author websites.`}, null, 2));
}
console.log(`Verified ${results.length} source previews and ${portraitResults.length} portrait previews.`);
