/* global window, document, getComputedStyle */
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
// Reuse the installed, pinned renderer's real composition initialization.
const rendererDir = path.dirname(require.resolve('@remotion/renderer'));
const {setPropsAndEnv} = require(path.join(rendererDir, 'set-props-and-env.js'));
const {seekToFrame} = require(path.join(rendererDir, 'seek-to-frame.js'));
const projectRoot = fileURLToPath(new URL('../../', import.meta.url));
const compositionId = 'NativeCopyFit';
const timeoutInMilliseconds = 10000;
let tempRoot;
let server;
let browser;
let serveUrl;

before(async () => {
  tempRoot = await mkdtemp(path.join(await realpath(os.tmpdir()), 'native-copy-fit-'));
  const bundleDir = await bundle({
    entryPoint: path.join(projectRoot, 'tests/video-production/fixtures/native-copy-fit.tsx'),
    rootDir: projectRoot, publicDir: path.join(tempRoot, 'empty-public'),
    outDir: path.join(tempRoot, 'bundle'), enableCaching: false,
    // Do not write webpack caches into the shared node_modules junction.
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
  if (tempRoot && path.basename(tempRoot).startsWith('native-copy-fit-')
    && path.dirname(tempRoot) === await realpath(os.tmpdir())) {
    await rm(tempRoot, {recursive: true, force: true});
  }
});

const inspect = async (input) => {
  const page = await browser.newPage({context: () => null, logLevel: 'error', indent: false,
    pageIndex: 0, onBrowserLog: () => {}, onLog: () => {}});
  try {
    const props = JSON.stringify(input);
    await page.setViewport({width: 1080, height: 1920, deviceScaleFactor: 1});
    await setPropsAndEnv({page, serveUrl, serializedInputPropsWithCustomSchema: props,
      envVariables: {}, initialFrame: 90, timeoutInMilliseconds, proxyPort: 0,
      retriesRemaining: 0, audioEnabled: false, videoEnabled: true, indent: false,
      logLevel: 'error', onServeUrlVisited: () => {}, isMainTab: true,
      mediaCacheSizeInBytes: null, initialMemoryAvailable: null, darkMode: false, sampleRate: 48000});
    await page.evaluate((serializedProps, id) => window.remotion_setBundleMode({
      type: 'composition', compositionName: id, serializedResolvedPropsWithSchema: serializedProps,
      compositionDurationInFrames: 180, compositionFps: 30, compositionHeight: 1920,
      compositionWidth: 1080, compositionDefaultCodec: null, compositionDefaultOutName: null,
      compositionDefaultVideoImageFormat: null, compositionDefaultPixelFormat: null,
      compositionDefaultProResProfile: null, compositionDefaultSampleRate: null,
    }), props, compositionId);
    await seekToFrame({frame: 90, page, composition: compositionId, timeoutInMilliseconds,
      indent: false, logLevel: 'error', attempt: 0});
    return await page.evaluate((values) => {
      // Native Talkcraft CSS is isolated in real ShadowRoots; inspect those too.
      const all = (root, selector) => [...root.querySelectorAll(selector),
        ...[...root.querySelectorAll('*')].flatMap((node) => node.shadowRoot ? all(node.shadowRoot, selector) : [])];
      const error = document.querySelector('[role="alert"]')?.textContent ?? null;
      const valueNodes = (values ?? []).map((text) => {
        const node = [...document.querySelectorAll('[data-copy-fit="data"] div')]
          .find((candidate) => candidate.textContent === text && candidate.childElementCount === 0);
        if (!node) throw new Error(`Missing rendered data value ${text}`);
        const range = document.createRange();
        range.selectNodeContents(node);
        const card = node.parentElement.getBoundingClientRect();
        const style = getComputedStyle(node);
        return {text: node.textContent, fontSize: Number.parseFloat(style.fontSize),
          lineRects: [...range.getClientRects()].map((rect) => ({
            top: rect.top, width: rect.width,
            overflow: Math.max(0, card.left - rect.left, rect.right - card.right,
              card.top - rect.top, rect.bottom - card.bottom),
          }))};
      });
      const caption = all(document, '.talkcraft-native-title .caption')[0];
      return {error, values: valueNodes,
        caption: caption?.textContent ?? null, keyword: caption?.querySelector('.kw')?.textContent ?? null};
    }, input.values && !input.expectError ? input.values : undefined);
  } finally {
    await page.close();
  }
};

for (const firstValue of ['两周', '2026年4月·两周']) {
  test(`DataAdapter keeps complete values and units on one painted line (${firstValue})`, async () => {
    const values = [firstValue, '至少36000人', '5800+个', '约345万条'];
    const result = await inspect({scenario: 'data', values});
    assert.equal(result.error, null);
    assert.deepEqual(result.values.map((node) => node.text), values, 'values must not be truncated or omitted');
    for (const node of result.values) {
      assert.equal(node.lineRects.length, 1, `${JSON.stringify(node)} must occupy one actual browser text line`);
      assert.ok(node.fontSize >= 24, `${node.text} must respect the existing minimum font size`);
      assert.ok(node.lineRects[0].overflow <= 1, `${JSON.stringify(node)} must fit its actual card`);
    }
  });
}

test('DataAdapter reports an explicit error when a complete value cannot fit at the minimum font size', async () => {
  const result = await inspect({scenario: 'data', values: ['9'.repeat(10000) + '人'], expectError: true});
  assert.match(result.error ?? '', /Text exceeds the safe area\. Shorten this field or split it into more shots\./);
});

test('keyword mapping renders an identical title and keyword only once', async () => {
  const result = await inspect({scenario: 'keyword', title: '同一个Claude', keyword: '同一个Claude'});
  assert.equal(result.error, null);
  assert.equal(result.caption, '同一个Claude');
  assert.equal(result.keyword, '同一个Claude');
});

test('keyword mapping preserves a distinct prefix and the body suffix', async () => {
  const result = await inspect({scenario: 'keyword', title: '同一个', keyword: 'Claude', body: '，真人接视频'});
  assert.equal(result.error, null);
  assert.equal(result.caption, '同一个Claude，真人接视频');
  assert.equal(result.keyword, 'Claude');
});

test('keyword mapping retains the body suffix when an identical prefix is removed', async () => {
  const result = await inspect({scenario: 'keyword', title: '同一个Claude', keyword: '同一个Claude', body: '，真人接视频'});
  assert.equal(result.error, null);
  assert.equal(result.caption, '同一个Claude，真人接视频');
  assert.equal(result.keyword, '同一个Claude');
});
