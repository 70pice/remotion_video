import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile, readdir, writeFile} from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const readJson = async (file) => JSON.parse(await readFile(path.join(root,file), 'utf8'));
const {components} = await readJson('docs/component-paths.json');
const {components:usage} = await readJson('docs/component-use-guide.json');
const payload = await readJson('.runtime/component-path-workbook.json');
const usageById = new Map(usage.map((component) => [component.compositionId,component]));
assert.equal(components.length,152);
assert.equal(new Set(components.map((component) => component.compositionId)).size,152);
assert.equal(usage.length,152);
assert.equal(usageById.size,152);
for (const orientation of ['vertical','horizontal']) {
  assert.equal(new Set(components.map((component) => component[`${orientation}Path`])).size,152);
  for (const component of components) {
    for (const key of [`${orientation}Path`, `${orientation}SourcePath`]) {
      const relative = component[key];
      assert.ok(relative.startsWith(`src/components/component-${orientation}/`), `${key}: ${relative}`);
      assert.ok(!path.isAbsolute(relative) && !relative.split('/').includes('..'), relative);
      await readFile(path.join(root,relative));
    }
    const entry = await readFile(path.join(root,component[`${orientation}Path`]),'utf8');
    assert.ok(entry.includes(`item.id === '${component.compositionId}'`), component.compositionId);
  }
}
const expectedRows = components.map((component) => {
  const guide = usageById.get(component.compositionId);
  assert.ok(guide?.description && guide?.useCase,component.compositionId);
  return [component.name,component.verticalPath,component.horizontalPath,guide.description,guide.useCase];
});
assert.deepEqual(payload.sheets[0].columns,['组件名称','竖版相对文件路径','横版相对文件路径','适合表达的内容','适用场景']);
assert.deepEqual(payload.sheets[0].data,expectedRows);
assert.deepEqual(payload.sheets[2].data,expectedRows.filter((row) => row[0].startsWith('Talkcraft / ')));
const manifest = await readJson('licenses/community/video-talkcraft/source-manifest.json');
assert.equal(manifest.files.length,108);
for (const file of manifest.files) {
  assert.equal(createHash('sha256').update(await readFile(path.join(root,file.localPath))).digest('hex'),file.sha256,file.slug);
}
const remaining = await readdir(path.join(root,'src/components/community'),{withFileTypes:true});
assert.equal(remaining.filter((entry) => entry.isDirectory()).length,0,'Stale implementation folders in community');
const report = {status:'passed',componentPairs:152,uniqueEntries:304,preservedSourceCount:108};
if (process.argv.includes('--compare-render-baseline')) {
  const before = await readJson('.runtime/component-organization-before.json');
  const after = await readJson('out/components/verification.json');
  const previous = new Map([...before.results,...before.portraitResults].map((item) => [item.id,item]));
  const current = [...after.results,...after.portraitResults];
  assert.equal(current.length,304);
  let unchanged = 0;
  for (const item of current) {
    assert.equal(item.status,'passed',item.id);
    const old = previous.get(item.id);
    assert.ok(old,item.id);
    if (item.id === 'Bits-ChatConversation') {
      assert.equal(item.width,1280); assert.equal(item.height,720);
      assert.equal(item.fps,old.fps); assert.equal(item.durationInFrames,old.durationInFrames);
      continue;
    }
    for (const field of ['width','height','fps','durationInFrames','frames','frameHashes']) assert.deepEqual(item[field],old[field],`${item.id} ${field}`);
    unchanged++;
  }
  report.renderComparison = {unchangedCompositions:unchanged,unchangedStills:unchanged*3,horizontalChatPreviewReframed:true};
}
await writeFile(path.join(root,'.runtime/component-path-integrity.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report));
