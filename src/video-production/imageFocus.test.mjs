import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import path from 'node:path';
import process from 'node:process';
import test from 'node:test';
import ts from 'typescript';

const root = process.cwd();
const nodeRequire = createRequire(import.meta.url);
const modules = new Map();
const load = async (file) => {
  if (modules.has(file)) return modules.get(file);
  const source = await readFile(file, 'utf8');
  const dependencies = {};
  for (const match of source.matchAll(/from ['"](\.\/[^'"]+)['"]/g)) {
    const dependency = path.resolve(path.dirname(file), match[1] + '.ts');
    dependencies[match[1]] = await load(dependency);
  }
  const module = {exports: {}};
  const code = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  }}).outputText;
  new Function('require', 'module', 'exports', code)((name) => dependencies[name] ?? nodeRequire(name), module, module.exports);
  modules.set(file, module.exports);
  return module.exports;
};
const {resolveImageFocusGeometry: resolve} = await load(path.join(root, 'src/video-production/adapters/imageFocusGeometry.ts'));
const base = {viewportWidth: 900, viewportHeight: 750, metadata: {width: 1200, height: 600}};
const cues = [{frame: 0}, {frame: 90, region: {x: 0.5, y: 0.2, width: 0.4, height: 0.6}}, {frame: 240}];

test('overview preserves a landscape figure and returns to the same geometry after focus', () => {
  const opening = resolve({...base, cues, frame: 0});
  assert.deepEqual(opening.image, {left: 0, top: 150, width: 900, height: 450});
  assert.equal(opening.emphasis, 0);
  const returned = resolve({...base, cues, frame: 258});
  assert.deepEqual(returned.image, opening.image);
  assert.equal(returned.emphasis, 0);
});

test('camera keeps the source aspect ratio and measured spotlight centered during zoom', () => {
  const focused = resolve({...base, cues, frame: 108});
  assert.equal(focused.image.width / focused.image.height, 2);
  assert.equal(focused.spotlight.width, 900);
  assert.ok(Math.abs(focused.spotlight.left) < 1e-10);
  assert.ok(Math.abs(focused.spotlight.top + focused.spotlight.height / 2 - 375) < 1e-10);
  assert.equal(focused.emphasis, 1);
});

test('a new caption cue starts from the previous view without an image jump or entrance restart', () => {
  const before = resolve({...base, cues, frame: 89});
  const start = resolve({...base, cues, frame: 90});
  assert.deepEqual(start.image, before.image);
  const halfway = resolve({...base, cues, frame: 99});
  const completed = resolve({...base, cues, frame: 108});
  assert.ok(halfway.image.width > start.image.width && halfway.image.width < completed.image.width);
  assert.equal(halfway.image.width / halfway.image.height, 2);
  assert.equal(halfway.emphasis, 0.5);
  const secondFocus = [...cues.slice(0, 2), {frame: 180, region: {x: 0.1, y: 0.1, width: 0.3, height: 0.5}}];
  assert.deepEqual(resolve({...base, cues: secondFocus, frame: 180}).image, completed.image);
});
