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

/* global window, document, getComputedStyle */

const require = createRequire(import.meta.url);
const rendererDir = path.dirname(require.resolve('@remotion/renderer'));
const {setPropsAndEnv} = require(path.join(rendererDir, 'set-props-and-env.js'));
const {seekToFrame} = require(path.join(rendererDir, 'seek-to-frame.js'));
const projectRoot = fileURLToPath(new URL('../../', import.meta.url));
const timeoutInMilliseconds = 10000;
let tempRoot;
let server;
let browser;
let serveUrl;

before(async () => {
  tempRoot = await mkdtemp(path.join(await realpath(os.tmpdir()), 'pip-text-fit-'));
  const bundleDir = await bundle({
    entryPoint: path.join(projectRoot, 'tests/video-production/fixtures/pip-text-fit.tsx'),
    rootDir: projectRoot, publicDir: path.join(tempRoot, 'empty-public'),
    outDir: path.join(tempRoot, 'bundle'), enableCaching: false,
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
      response.writeHead(200, {'Content-Type': target.endsWith('.js') ? 'application/javascript'
        : target.endsWith('.html') ? 'text/html' : 'application/octet-stream'}).end(content);
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
  if (tempRoot && path.basename(tempRoot).startsWith('pip-text-fit-')
    && path.dirname(tempRoot) === await realpath(os.tmpdir())) {
    await rm(tempRoot, {recursive: true, force: true});
  }
});

const measure = async ({title, source = '', layered = false}) => {
  const page = await browser.newPage({context: () => null, logLevel: 'error', indent: false,
    pageIndex: 0, onBrowserLog: null, onLog: () => {}});
  try {
    const props = JSON.stringify({title, source, layered});
    await page.setViewport({width: 1080, height: 1920, deviceScaleFactor: 1});
    await setPropsAndEnv({page, serveUrl, serializedInputPropsWithCustomSchema: props,
      envVariables: {}, initialFrame: 48, timeoutInMilliseconds, proxyPort: 0,
      retriesRemaining: 0, audioEnabled: false, videoEnabled: true, indent: false,
      logLevel: 'error', onServeUrlVisited: () => {}, isMainTab: true,
      mediaCacheSizeInBytes: null, initialMemoryAvailable: null, darkMode: false, sampleRate: 48000});
    await page.evaluate((serializedProps) => window.remotion_setBundleMode({
      type: 'composition', compositionName: 'PipTextFit', serializedResolvedPropsWithSchema: serializedProps,
      compositionDurationInFrames: 180, compositionFps: 30, compositionHeight: 1920,
      compositionWidth: 1080, compositionDefaultCodec: null, compositionDefaultOutName: null,
      compositionDefaultVideoImageFormat: null, compositionDefaultPixelFormat: null,
      compositionDefaultProResProfile: null, compositionDefaultSampleRate: null,
    }), props);
    await seekToFrame({frame: 48, page, composition: 'PipTextFit', timeoutInMilliseconds,
      indent: false, logLevel: 'error', attempt: 0});
    return await page.evaluate((copy) => {
      const candidates = [...document.querySelectorAll('div')].filter((element) =>
        element.textContent === copy.title && element.childElementCount === 0);
      const element = candidates.find((node) => getComputedStyle(node.parentElement).display === 'grid');
      if (!element) throw new Error('Actual community primary title was not mounted');
      let card = element.parentElement;
      while (card && getComputedStyle(card).overflow !== 'hidden') card = card.parentElement;
      if (!card) throw new Error('Missing actual clipping card');
      const bounds = card.getBoundingClientRect();
      const fields = [element, ...[...card.querySelectorAll('div')].filter((node) =>
        copy.source && node.textContent === copy.source && node.childElementCount === 0)];
      return {cardWidth: bounds.width, fields: fields.map((node) => {
        const range = document.createRange();
        range.selectNodeContents(node);
        return {text: node.textContent, fontSize: getComputedStyle(node).fontSize,
          fieldWidth: node.getBoundingClientRect().width,
          rects: [...range.getClientRects()].map((rect) => ({
            left: Math.max(0, bounds.left - rect.left), right: Math.max(0, rect.right - bounds.right),
            top: Math.max(0, bounds.top - rect.top), bottom: Math.max(0, rect.bottom - bounds.bottom),
          }))};
      })};
    }, {title, source});
  } finally {
    await page.close();
  }
};

const assertFits = (result, expectedCardWidth = 768) => {
  assert.equal(result.cardWidth, expectedCardWidth);
  assert.ok(parseFloat(result.fields[0].fontSize) >= 32, 'Keep the tested title legible on a phone');
  for (const field of result.fields) {
    assert.ok(field.rects.length);
    for (const rect of field.rects) {
      assert.ok(Object.values(rect).every((pixels) => pixels <= 1),
        `Actual ${field.text} (${field.fontSize}, width ${field.fieldWidth}) clips in ${result.cardWidth}px card: ${JSON.stringify(rect)}`);
    }
  }
};

test('portrait pip title fits the actual narrow card instead of the full stage width', async () => {
  assertFits(await measure({title: '日常任务：写笔记、搜索、归档'}));
});

test('portrait pip short-copy control remains readable inside the same card', async () => {
  assertFits(await measure({title: '日常任务'}));
});

test('portrait pip source text stays inside the actual clipping card', async () => {
  assertFits(await measure({title: '日常任务', source: '同类日常工具界面示意，非报告中的应用；画面仅说明机制'}));
});

test('portrait layered pip retains its full-width geometry', async () => {
  assertFits(await measure({title: '日常任务：写笔记、搜索、归档', layered: true}), 936);
});
