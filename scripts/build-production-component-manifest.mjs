import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const root = process.cwd();
const output = path.join(root, 'videoagents', 'component-manifest.json');
const libraries = [
  {key: 'snapcn', name: 'Snapcn'},
  {key: 'rve', name: 'RVE'},
  {key: 'remocn', name: 'Remocn'},
  {key: 'remotion-ui', name: 'RemotionUI'},
  {key: 'bits', name: 'Bits'},
  {key: 'video-talkcraft', name: 'Talkcraft'},
];

const semantic = [
  ['title', '冲击标题', '主题与开场钩子', '开头与章节'],
  ['keyword', '关键词', '突出旁白重音', '短观点和关键词'],
  ['evidence', '证据截图', '真实截图和来源', '事实证据与原文高亮'],
  ['image_focus', '图片聚焦', '真实图片慢推近', '现场与概念素材'],
  ['comparison', '前后对比', '两个观点或状态并列', '有来源的对比'],
  ['data', '数据卡', '展示已核验数字', '有来源的 1 到 4 个指标'],
  ['steps', '步骤时间线', '顺序呈现过程', '1 到 4 个步骤'],
  ['conclusion', '结论卡', '总结与行动提示', '片尾与段落收束'],
  ['video', '真实视频', '播放已导入的真实视频片段', '官方演示、实拍、录屏或新闻视频素材'],
].map(([componentId, name, description, useCase]) => ({
  component_id: componentId,
  name,
  description,
  use_case: useCase,
  library: 'VideoAgents',
  orientation: 'both',
  kind: 'adapter',
  props_mode: 'typed',
  production_ready: true,
  min_frames: 15,
  allowed_usages: ['personal', 'commercial', 'unspecified'],
  license_note: '本项目新增的参数化画面；所用图片和字体须另行核验',
}));

const guidance = JSON.parse(
  await readFile(path.join(root, 'docs', 'component-use-guide.json'), 'utf8'),
).components;
const guideById = new Map(guidance.map((entry) => [entry.compositionId, entry]));
const community = [];
for (const library of libraries) {
  const rows = JSON.parse(
    await readFile(
      path.join(root, 'src', 'components', 'community', `catalog-${library.key}.json`),
      'utf8',
    ),
  );
  for (const row of rows) {
    const guide = guideById.get(row.compositionId);
    if (!guide?.description || !guide?.useCase) {
      throw new Error(`Missing production guidance: ${row.compositionId}`);
    }
    community.push({
      component_id: row.compositionId,
      name: `${library.name} / ${row.name}`,
      description: guide.description,
      use_case: guide.useCase,
      library: library.name,
      orientation: 'both',
      kind: 'preset',
      props_mode: 'empty',
      production_ready: true,
      min_frames: 15,
      allowed_usages: library.name === 'Talkcraft'
        ? ['personal', 'unspecified']
        : ['personal', 'commercial', 'unspecified'],
      license_note: row.licenseNote,
      slug: row.slug,
    });
  }
}

const entries = [...semantic, ...community];
const ids = new Set(entries.map((entry) => entry.component_id));
if (semantic.length !== 9 || community.length !== 152 || ids.size !== 161) {
  throw new Error(`Expected 9 adapters + 152 presets = 161 unique IDs, got ${ids.size}`);
}
for (const entry of entries) {
  if (!/^[A-Za-z0-9_-]{1,100}$/.test(entry.component_id)) {
    throw new Error(`Unsafe component ID: ${entry.component_id}`);
  }
}

const content = JSON.stringify({schema_version: '1', entries}, null, 2) + '\n';
if (process.argv.includes('--check')) {
  const current = await readFile(output, 'utf8').catch(() => '');
  if (current !== content) {
    console.error('videoagents/component-manifest.json is stale; run npm run generate:production-components');
    process.exitCode = 1;
  }
} else {
  await writeFile(output, content);
  console.log(`Wrote ${path.relative(root, output)} with 9 adapters and 152 production presets.`);
}
