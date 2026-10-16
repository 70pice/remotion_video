import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {mkdtemp, readFile, realpath, rm} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath, URL} from 'node:url';
import {after, before, test} from 'node:test';
import {bundle} from '@remotion/bundler';
import {openBrowser} from '@remotion/renderer';

const require = createRequire(import.meta.url);
// Use the installed renderer's initialization/seeking rather than simulate
// Remotion hooks. Version is already pinned by the repository.
const rendererDir = path.dirname(require.resolve('@remotion/renderer'));
const {setPropsAndEnv} = require(path.join(rendererDir, 'set-props-and-env.js'));
const {seekToFrame} = require(path.join(rendererDir, 'seek-to-frame.js'));
const projectRoot = fileURLToPath(new URL('../../', import.meta.url));
const compositionId = 'ProductionTextFit';
const timeoutInMilliseconds = 10000;
let tempRoot;
let server;
let browser;
let serveUrl;

before(async () => {
  tempRoot = await mkdtemp(path.join(await realpath(os.tmpdir()), 'production-text-fit-'));
  const bundleDir = await bundle({
    entryPoint: path.join(projectRoot, 'tests/video-production/fixtures/production-text-fit.tsx'),
    rootDir: projectRoot, publicDir: path.join(tempRoot, 'empty-public'),
    outDir: path.join(tempRoot, 'bundle'), enableCaching: false,
    // The shared node_modules junction must remain read-only.
    webpackOverride: (config) => ({...config, cache: false}),
  });
  server = createServer(async (request, response) => {
    try {
      const requestPath = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      const target = path.resolve(bundleDir, `.${requestPath === '/' ? '/index.html' : requestPath}`);
      const relative = path.relative(bundleDir, target);
      if (relative.startsWith('..') || path.isAbsolute(relative)) {
        response.writeHead(403).end();
        return;
      }
      // Barrel imports load bundled community fonts even when only these two
      // adapters mount. Serve tracked fonts read-only; never copy task media.
      const content = requestPath.startsWith('/public/community/fonts/')
        ? await readFile(path.join(projectRoot, 'public', requestPath.slice('/public/'.length)))
        : await readFile(target);
      const type = target.endsWith('.js') ? 'application/javascript'
        : target.endsWith('.css') ? 'text/css' : target.endsWith('.html') ? 'text/html' : 'application/octet-stream';
      response.writeHead(200, {'Content-Type': type}).end(content);
    } catch {
      response.writeHead(404).end();
    }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  serveUrl = `http://127.0.0.1:${server.address().port}`;
  browser = await openBrowser('chrome', {logLevel: 'error'});
});

after(async () => {
  await browser?.close({silent: true});
  if (server) await new Promise((resolve) => server.close(resolve));
  // Never recursively clean a computed path without checking its workspace.
  if (tempRoot && path.basename(tempRoot).startsWith('production-text-fit-')
    && path.dirname(tempRoot) === await realpath(os.tmpdir())) {
    await rm(tempRoot, {recursive: true, force: true});
  }
});

const measure = async (scenario, items, frames = [48, 108, 168], options = {}) => {
  const page = await browser.newPage({context: () => null, logLevel: 'error', indent: false,
    pageIndex: 0, onBrowserLog: null, onLog: () => {}});
  try {
    const props = JSON.stringify({scenario, ...(items ? {items} : {}), ...options});
    await page.setViewport({width: 1080, height: 1920, deviceScaleFactor: 1});
    await setPropsAndEnv({page, serveUrl, serializedInputPropsWithCustomSchema: props,
      envVariables: {}, initialFrame: frames[0], timeoutInMilliseconds, proxyPort: 0,
      retriesRemaining: 0, audioEnabled: false, videoEnabled: true, indent: false,
      logLevel: 'error', onServeUrlVisited: () => {}, isMainTab: true,
      mediaCacheSizeInBytes: null, initialMemoryAvailable: null, darkMode: false, sampleRate: 48000});
    await page.evaluate((serializedProps, id) => window.remotion_setBundleMode({
      type: 'composition', compositionName: id, serializedResolvedPropsWithSchema: serializedProps,
      compositionDurationInFrames: 360, compositionFps: 30, compositionHeight: 1920,
      compositionWidth: 1080, compositionDefaultCodec: null, compositionDefaultOutName: null,
      compositionDefaultVideoImageFormat: null, compositionDefaultPixelFormat: null,
      compositionDefaultProResProfile: null, compositionDefaultSampleRate: null,
    }), props, compositionId);
    const measurements = [];
    for (const frame of frames) {
      await seekToFrame({frame, page, composition: compositionId, timeoutInMilliseconds,
        indent: false, logLevel: 'error', attempt: 0});
      measurements.push(await page.evaluate((atFrame, onlyNativeId) => {
        const rectOf = (rect) => ({left: rect.left, top: rect.top, right: rect.right,
          bottom: rect.bottom, width: rect.width, height: rect.height});
        const outside = (rect, slot) => ({
          left: Math.max(0, slot.left - rect.left), top: Math.max(0, slot.top - rect.top),
          right: Math.max(0, rect.right - slot.right), bottom: Math.max(0, rect.bottom - slot.bottom),
        });
        const report = [];
        for (const nativeId of ['Rve-ProgressSteps', 'Snapcn-WordFlip']) {
          if (onlyNativeId && nativeId !== onlyNativeId) continue;
          const slot = document.querySelector(`[data-set-part][data-native-id="${nativeId}"]`);
          if (!slot) throw new Error(`Missing real production slot ${nativeId}`);
          const slotRect = slot.getBoundingClientRect();
          const selector = nativeId === 'Rve-ProgressSteps'
            ? '[data-progress-step-label], [data-progress-step-circle]' : '[data-word-flip-word]';
          const nodes = [...slot.querySelectorAll(selector)].map((element) => {
            const style = getComputedStyle(element);
            const range = document.createRange();
            range.selectNodeContents(element);
            const rects = element.hasAttribute('data-progress-step-circle')
              ? [element.getBoundingClientRect()] : [...range.getClientRects()];
            return {kind: element.hasAttribute('data-progress-step-circle') ? 'step-circle' : 'text',
              text: element.textContent, fontSize: style.fontSize, opacity: Number(style.opacity),
              fontWeight: Number(style.fontWeight),
              rects: rects.map((rect) => ({...rectOf(rect), overflow: outside(rect, slotRect)}))};
          });
          report.push({nativeId, slot: rectOf(slotRect), nodes,
            ready: slot.querySelector('[data-word-flip-ready]')?.getAttribute('data-word-flip-ready')});
        }
        return {frame: atFrame, report, delayHandles: window.remotion_delayRenderHandles.length};
      }, frame, options.onlyNativeId ?? null));
    }
    return measurements;
  } finally {
    await page.close();
  }
};

const assertFits = (scenario, measurements, onlyNativeId) => {
    const failures = [];
    for (const {frame, report, delayHandles} of measurements) {
      assert.equal(delayHandles, 0, 'actual layout must be committed before Remotion marks the frame ready');
      for (const {nativeId, slot, nodes} of report) {
        if (onlyNativeId && nativeId !== onlyNativeId) continue;
        if (nativeId === 'Snapcn-WordFlip') assert.equal(report.find((entry) => entry.nativeId === nativeId).ready, 'true');
        if (nativeId !== 'Snapcn-WordFlip' || frame >= 43) {
          assert.ok(nodes.length > 0, `${nativeId} must expose actual painted nodes at frame ${frame}`);
        }
        for (const node of nodes) {
          if (node.kind === 'text') {
            assert.ok(parseFloat(node.fontSize) >= (nativeId === 'Snapcn-WordFlip' ? 42 : 34), 'phone-readable production text floor');
            assert.ok(node.rects.length <= 2, 'at most two lines of real text per step/word');
            assert.ok(node.fontWeight >= 600);
          }
          assert.ok(node.rects.length > 0, `${nativeId} ${node.text} has no browser text bounds`);
          for (const rect of node.rects) {
            if (Object.values(rect.overflow).some((pixels) => pixels > 1)) {
              failures.push({frame, nativeId, slot: [slot.width, slot.height], kind: node.kind,
                text: node.text, fontSize: node.fontSize,
                overflow: Object.fromEntries(Object.entries(rect.overflow).map(([edge, px]) => [edge, Number(px.toFixed(2))]))});
            }
          }
        }
      }
    }
    const byNode = new Map();
    for (const failure of failures) {
      const key = `${failure.nativeId} ${failure.kind} ${failure.text}`;
      const previous = byNode.get(key);
      byNode.set(key, {...failure, overflow: Object.fromEntries(Object.entries(failure.overflow)
        .map(([edge, px]) => [edge, Math.max(px, previous?.overflow[edge] ?? 0)]))});
    }
    const summary = [...byNode.values()].map((failure) =>
      `${failure.nativeId} ${failure.slot.join('x')} ${failure.kind} ${JSON.stringify(failure.text)} ${failure.fontSize}`
      + ` overflow_px=${JSON.stringify(failure.overflow)}`).join('\n');
    assert.equal(failures.length, 0, `${scenario} real DOM overflow:\n${summary}`);
};

test('A02: original long steps reject the 456x210 slot explicitly', async () => {
  await assert.rejects(measure('A02', undefined, [48], {onlyNativeId: 'Rve-ProgressSteps'}), /ProgressSteps production slot 456x210 cannot fit/);
});

test('A02: increasing step slot space displays the complete original copy', async () => {
  assertFits('A02 with space', await measure('A02', undefined, [48, 108, 168], {stepHeight: 320}));
});

test('B12: original short slots show the complete copy and steps', async () => {
  assertFits('B12', await measure('B12'));
});

const detailedReportSteps = ['示例说明：CASE-0001', '国内产品设计组用Widget开发', '30多款工具App·用户在本地'];

test('B12: detailed mixed-language steps reject the 476x220 slot', async () => {
  await assert.rejects(measure('B12', detailedReportSteps, [48], {onlyNativeId: 'Rve-ProgressSteps'}),
    /ProgressSteps production slot 476x220 cannot fit/);
});

test('B12: more height preserves complete detailed steps at the readable font floor', async () => {
  assertFits('B12 detailed steps with space', await measure('B12', detailedReportSteps, [48, 108, 168], {
    onlyNativeId: 'Rve-ProgressSteps', stepHeight: 320,
  }));
});

test('minimal: three one-character steps fit at 456x210', async () => {
  assertFits('A02 minimal steps', await measure('A02', ['一', '二', '三'], [168]), 'Rve-ProgressSteps');
});

test('control: removing one short step fits at 456x210', async () => {
  assertFits('A02 two-step control', await measure('A02', ['一', '二'], [168]), 'Rve-ProgressSteps');
});

test('minimal: one long mixed Chinese/Latin WordFlip fits at 456x220', async () => {
  assertFits('B12 minimal word', await measure('B12', ['用Widget开发30多款App'], [168]), 'Snapcn-WordFlip');
});

test('WordFlip: original A02 words fit during measurement, flips, and every settled word', async () => {
  const frames = [0, 14, 18, 22, 28, 32, 38, 43, 48, 74, 78, 82, 88, 92, 98, 103, 108, 134, 138, 142, 148, 152, 158, 163, 168];
  assertFits('A02 word motion', await measure('A02', undefined, frames, {onlyNativeId: 'Snapcn-WordFlip'}));
});

test('WordFlip: dimension and text changes remeasure before the next frame is ready', async () => {
  assertFits('B12 dynamic words', await measure('B12', ['短词', '另一词', '最后'], [48, 108, 168], {
    onlyNativeId: 'Snapcn-WordFlip', wordWidth: 600, changedAtFrame: 90, nextWordWidth: 456,
    nextItems: ['国内产品设计组', '用Widget开发30多款App', '目标用户在本地'],
  }));
});

test('WordFlip: impossible two-line capacity rejects instead of clipping', async () => {
  await assert.rejects(measure('B12', undefined, [48], {onlyNativeId: 'Snapcn-WordFlip', wordWidth: 200, wordHeight: 110}),
    /WordFlip production slot 200x110 cannot fit/);
});

test('control: one short WordFlip phrase fits at 456x220', async () => {
  assertFits('B12 short-word control', await measure('B12', ['目标用户在本地'], [168]), 'Snapcn-WordFlip');
});

test('standalone WordFlip keeps its original 72px single-line equal-width words', async () => {
  const measurements = await measure('B12', undefined, [108, 143, 178], {onlyNativeId: 'Snapcn-WordFlip', standalone: true});
  const words = measurements.map(({report}) => report[0].nodes[0]);
  assert.deepEqual(words.map((word) => word.text), ['Modern', 'Stunning', 'Minimal']);
  for (const word of words) {
    assert.equal(word.fontSize, '72px');
    assert.equal(word.fontWeight, 600);
    assert.equal(word.rects.length, 1);
  }
  const widths = words.map((word) => word.rects[0].width);
  assert.ok(Math.max(...widths) - Math.min(...widths) < 2, 'standalone fitScales still equalizes the actual painted widths');
});
/* global window, document, getComputedStyle */
