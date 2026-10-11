import {readFile, writeFile, access} from 'node:fs/promises';
import ts from 'typescript';

const root = new URL('../', import.meta.url);
const readSource = async (path) => ts.createSourceFile(path, await readFile(new URL(path, root), 'utf8'),
  ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const literal = (node) => {
  if (!node) return undefined;
  if (ts.isStringLiteral(node) || ts.isNumericLiteral(node)) return ts.isNumericLiteral(node) ? Number(node.text) : node.text;
  if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (ts.isArrayLiteralExpression(node)) return node.elements.map(literal);
  if (ts.isObjectLiteralExpression(node)) return Object.fromEntries(node.properties
    .filter(ts.isPropertyAssignment).map((prop) => [prop.name.getText().replace(/^['"]|['"]$/g, ''), literal(prop.initializer)]));
  if (ts.isAsExpression(node) || ts.isSatisfiesExpression(node)) return literal(node.expression);
  return undefined;
};
const array = (source, name) => {
  let result;
  const visit = (node) => {
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === name) result = literal(node.initializer);
    ts.forEachChild(node, visit);
  };
  visit(source);
  if (!Array.isArray(result)) throw new Error(`Missing literal native bindings array: ${name}`);
  return result;
};
const kebab = (name) => name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
const titleConstraints = (binding) => {
  const declared = binding.content_constraints ?? [];
  if (!Array.isArray(declared)) return declared;
  const result = {};
  for (const constraint of declared) {
    if (constraint === 'body_required' || constraint === 'body_or_items_1_required'
      || constraint.includes('lines_min_2') || constraint.includes('lines_min_3')) result.body_required = true;
    if (constraint === 'keyword_required') result.keyword_required = true;
    if (constraint === 'selected_option_must_match_title_or_keyword') result.selection_matches_item = true;
    if (constraint.includes('lines_min_3')) result.items_min = Math.max(result.items_min ?? 0, 1);
    const minimum = constraint.match(/^items_min_(\d+)$/);
    if (minimum) result.items_min = Math.max(result.items_min ?? 0, Number(minimum[1]));
    const visibleFrames = constraint.match(/^min_visible_frames_(\d+)$/);
    if (visibleFrames) result.min_visible_frames = Number(visibleFrames[1]);
    if (constraint.startsWith('numeric_first_item')) {result.items_min = Math.max(result.items_min ?? 0, 1); result.numeric_first_item = true;}
    if (constraint.startsWith('from_text_')) result.replacement_required = true;
  }
  return result;
};
const entries = [
  {component_id: 'Snapcn-PhoneFrame', roles: ['main'], source: 'src/components/component-horizontal/snapcn/phone-frame/index.tsx', renderer: 'PhoneFrameMaterial', use_case: '本期真实App界面的原生手机框，不模拟真实视频', content_constraints: {media_required: true}},
  ...[['RemotionUI-SocialClip', 'social-clip'], ['RenderComp-SocialReel', 'social-reel']].map(([id, variant]) =>
    ({component_id: id, roles: ['main'], source: 'src/components/component-horizontal/curated/CuratedScene.tsx', renderer: `CuratedScene:${variant}`, use_case: '竖屏清晰大幅真实素材，不能当作真实视频', content_constraints: {media_required: true}})),
  {component_id: 'RenderComp-KpiCounter', roles: ['main'], source: 'src/components/component-horizontal/curated/CuratedScene.tsx', renderer: 'CuratedScene:kpi-counter', use_case: '真实指标，必须给metric.label/value，保留原文单位和口径', content_constraints: {metric_required: true}},
];
const snapcnIds = array(await readSource('src/video-production/SnapcnNativeTitles.tsx'), 'snapcnNativeTitleIds');
for (const id of snapcnIds) entries.push({component_id: id,
  roles: /SearchTyping|PromptSend|AnswerStream/.test(id) ? ['title'] : ['title', 'emphasis'],
  source: `src/components/component-horizontal/snapcn/${kebab(id.slice(7))}/index.tsx`,
  renderer: `SnapcnNativeTitle:${id.slice(7)}`,
  use_case: /PromptSend|Answer/.test(id) ? '已确认旁白的机制示意；不能编人物对话或冒充真实App，不改原字幕时间' : '短标题或关键词强调，文字取自当前旁白，不改口播字幕',
  ...(/TextRewrite|TextSwap/.test(id) ? {content_constraints: {replacement_required: true}} : {}),
  ...(id === 'Snapcn-WordFlip' ? {content_constraints: {items_min: 2, items_distinct: true}} : {}),
  ...(/Answer/.test(id) ? {content_constraints: {body_required: true}} : {}),
});
const titleBindings = array(await readSource('src/video-production/TalkcraftNativeTitles.tsx'), 'talkcraftNativeTitleBindings');
for (const binding of titleBindings) entries.push({component_id: binding.id, roles: [binding.role],
  source: `src/components/component-horizontal/video-talkcraft/${binding.source}`,
  renderer: `TalkcraftNativeTitle:${binding.id.slice(10)}`, use_case: binding.motion,
  content_constraints: titleConstraints(binding),
});
const mediaSource = await readSource('src/video-production/NativeMediaScenes.tsx');
for (const binding of array(mediaSource, 'bindings')) {
  if (!binding.source) throw new Error(`${binding.component_id}: native source provenance is required`);
  entries.push({component_id: binding.component_id, roles: ['main'], source: binding.source,
    renderer: `NativeMediaScene:${binding.component_id}`, use_case: binding.use_case ?? `必须提供本期真实输入: ${(binding.requires ?? []).join(', ')}`,
    content_constraints: {...(binding.content_constraints ?? {}),
      ...(!binding.requires?.includes('image_media') ? {asset_forbidden: true} : {})},
  });
}
try {
  const cameraSource = await readSource('src/video-production/TalkcraftNativeMedia.tsx');
  for (const binding of array(cameraSource, 'talkcraftNativeMediaBindings')) entries.push({
    component_id: binding.id, roles: ['main'],
    source: binding.source.startsWith('src/') ? binding.source : `src/components/component-horizontal/video-talkcraft/${binding.source}`,
    renderer: `TalkcraftNativeMedia:${binding.id.slice(10)}`, use_case: binding.motion,
    content_constraints: {media_required: true, image_only: true, ...titleConstraints(binding)},
  });
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
const manifest = JSON.parse(await readFile(new URL('videoagents/component-manifest.json', root), 'utf8'));
const allowed = new Set(manifest.entries.filter((entry) => entry.kind === 'preset').map((entry) => entry.component_id));
const ids = new Set();
for (const entry of entries) {
  if (!allowed.has(entry.component_id) || ids.has(entry.component_id)) throw new Error(`Invalid/duplicate native binding ${entry.component_id}`);
  if (!entry.renderer || !entry.use_case) throw new Error(`Missing native metadata ${entry.component_id}`);
  ids.add(entry.component_id);
  await access(new URL(entry.source, root));
}
entries.sort((a, b) => a.component_id.localeCompare(b.component_id, 'en'));
const output = `${JSON.stringify({schema_version: '1', entries}, null, 2)}\n`;
const destination = new URL('videoagents/native-component-capabilities.json', root);
if (process.argv.includes('--check')) {
  if ((await readFile(destination, 'utf8')).replace(/\r\n/g, '\n') !== output) throw new Error('Native capabilities are stale; regenerate from real bindings');
} else await writeFile(destination, output, 'utf8');
console.log(`Verified ${entries.length} distinct native library bindings (${entries.filter((entry) => entry.roles.includes('main')).length} main, ${entries.filter((entry) => !entry.roles.includes('main')).length} title/emphasis).`);
