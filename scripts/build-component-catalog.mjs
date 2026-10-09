import {existsSync} from 'node:fs';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import './generate-component-entrypoints.mjs';

const root = process.cwd();
const expectedPresetCount = 187;
const expectedRegisteredCount = expectedPresetCount * 2;
const repositories = [
  {key: 'snapcn', name: 'Snapcn', count: 21, commit: '4399d249002afae506497cc90ac3f064e189127d', repo: 'snapcndev/snapcn', license: 'MIT（独立 LICENSE）', kind: '可复制的参数化视频组件', method: '复制组件与工具；部分离线 Inter / Source Serif 4 字体；本地示例素材', preview: 'https://snapcn.dev/docs/components'},
  {key: 'rve', name: 'RVE', count: 26, commit: '6209b724798e48ff395f8df1a6fa2d26082372b5', repo: 'reactvideoeditor/remotion-templates', license: 'README 声明 MIT；无独立 LICENSE', kind: '单文件视频模板', method: '复制选定模板，补基础 Props；保留原版并新增竖屏布局分支', preview: 'https://www.reactvideoeditor.com/remotion-templates'},
  {key: 'remocn', name: 'Remocn', count: 5, commit: '8ae853e4c08108105684d4b8cac7f22400840d2a', repo: 'Remocn/remocn', license: 'MIT（独立 LICENSE）', kind: '可复制的视频组件与工具', method: '复制组件及实际依赖闭包', preview: 'https://remocn.dev'},
  {key: 'remotion-ui', name: 'RemotionUI', count: 13, commit: 'b7e0e6becc3d22b8b03dfef72c064f72ff9fad1f', repo: 'riaz37/remotion-ui', license: 'MIT（独立 LICENSE）', kind: '通过 registry 分发的视频组件', method: '复制组件及工具；不安装整套网站', preview: 'https://remotionui.com/docs/components'},
  {key: 'bits', name: 'Bits', count: 4, commit: 'de35fda84b7b6acbe549a0b302a82ef211e8ef1e', repo: 'av/remotion-bits', license: 'package.json / README 声明 MIT；无独立 LICENSE', kind: '动画基础工具及组合示例', method: '复制四个示例及底层动画依赖闭包', preview: 'https://remotion-bits.dev/docs/bits/'},
  {key: 'rendercomp', name: 'RenderComp', count: 10, commit: 'f648980', repo: 'RenderComp/free-remotion-templates', license: 'README / package 声明 MIT', kind: '免费短视频模板', method: '精选可拆成镜头卡的模板，接入 CuratedScene 原生素材槽', preview: 'https://github.com/RenderComp/free-remotion-templates'},
  {key: 'video-talkcraft', name: 'Talkcraft', count: 108, commit: '4cd673df4b7a6a35784a0881df223721789c5e23', repo: 'Vincentwei1021/video-talkcraft', license: 'PolyForm Noncommercial 1.0.0', kind: 'Agent skill + Remotion 卡片 + 独立工作台', method: '108 张原始 TSX 字节保持；作者示例素材；按用户声明非商业用途导入', preview: 'https://vincentwei1021.github.io/video-talkcraft/'},
];
const components = [];
const paths = JSON.parse(await readFile(path.join(root, 'docs/component-paths.json'), 'utf8')).components;
const pathById = new Map(paths.map((component) => [component.compositionId, component]));
const usage = JSON.parse(await readFile(path.join(root, 'docs/component-use-guide.json'), 'utf8')).components;
const usageById = new Map(usage.map((component) => [component.compositionId, component]));
if (paths.length !== expectedPresetCount || pathById.size !== expectedPresetCount ||
  usage.length !== expectedPresetCount || usageById.size !== expectedPresetCount) {
  throw new Error(`Expected ${expectedPresetCount} path pairs and usage descriptions`);
}
for (const repo of repositories) {
  const rows = JSON.parse(await readFile(path.join(root, 'src/components/community', `catalog-${repo.key}.json`), 'utf8'));
  if (rows.length !== repo.count) throw new Error(`${repo.name}: unexpected component count`);
  for (const row of rows) {
    if (!existsSync(path.join(root, row.localPath))) throw new Error(`Missing source: ${row.localPath}`);
    components.push({...row, library: repo.name, repository: `https://github.com/${repo.repo}`, commit: repo.commit,
      sourceUrl: `https://github.com/${repo.repo}/blob/${repo.commit}/${row.sourcePath}`});
  }
}
const verification = JSON.parse(await readFile(path.join(root, 'out/components/verification.json'), 'utf8'));
if (verification.count !== expectedPresetCount || verification.portraitCount !== expectedPresetCount ||
  verification.registeredCount !== expectedRegisteredCount ||
  verification.portraitResults.some((r) => r.layout !== 'native-portrait' || r.frames.length !== 3) ||
  [...verification.results, ...verification.portraitResults].some((r) => r.status !== 'passed')) {
  throw new Error('Verified original and registered portrait previews must pass before delivery.');
}
const nativePortraitCount = verification.portraitCount;
const verified = new Map(verification.results.map((r) => [r.id, r]));
const portraitVerified = new Map(verification.portraitResults.map((r) => [r.id, r]));
for (const component of components) {
  const result = verified.get(component.compositionId);
  if (!result) throw new Error(`No render result for ${component.compositionId}`);
  component.verification = result;
  component.portraitVerification = portraitVerified.get(`Vertical-${component.compositionId}`);
  if (!component.portraitVerification) throw new Error(`Missing native portrait verification: ${component.compositionId}`);
  const entry = pathById.get(component.compositionId);
  const guide = usageById.get(component.compositionId);
  if (!entry || !guide || !guide.description || !guide.useCase) throw new Error(`Missing paths or usage: ${component.compositionId}`);
  component.portraitSourcePath = entry.verticalSourcePath;
  component.horizontalEntryPath = entry.horizontalPath;
  component.verticalEntryPath = entry.verticalPath;
  component.description = guide.description;
  component.sourceUseCase = component.useCase;
  component.useCase = guide.useCase;
  for (const file of [entry.verticalSourcePath, entry.horizontalSourcePath, entry.verticalPath, entry.horizontalPath]) {
    if (!existsSync(path.join(root,file))) throw new Error(`Missing component path: ${file}`);
  }
}
const talk = JSON.parse(await readFile(path.join(root, 'docs/video-talkcraft-catalog.json'), 'utf8'));
for (const card of talk.components) {
  const original = verified.get(card.compositionId);
  if (!original) throw new Error(`Missing Talkcraft verification: ${card.slug}`);
  card.integrationStatus = `已导入原源码；非商业用途；原版三帧/原生竖屏三帧通过；竖屏：Vertical-${card.compositionId}（1080×1920）；原版：${card.compositionId}`;
  card.verification = original;
  card.portraitCompositionId = portraitVerified.has(`Vertical-${card.compositionId}`) ? `Vertical-${card.compositionId}` : null;
  const entry = pathById.get(card.compositionId);
  card.localPath = entry.horizontalSourcePath;
  card.verticalEntryPath = entry.verticalPath;
  card.horizontalEntryPath = entry.horizontalPath;
}
await writeFile(path.join(root, 'docs/video-talkcraft-catalog.json'), JSON.stringify(talk, null, 2));
await mkdir(path.join(root, 'docs'), {recursive: true});
await mkdir(path.join(root, '.runtime'), {recursive: true});
await writeFile(path.join(root, 'docs/community-components.json'), JSON.stringify({checkedAt: verification.checkedAt, repositories, components}, null, 2));

const intro = [
  ['目录范围', '组件目录统一收录 187 个组件：Snapcn 21、RVE 26、Remocn 5、RemotionUI 13、Bits 4、RenderComp 10、Talkcraft 108。每行同时提供竖版、横版入口及表达内容、使用场景。Talkcraft 子表保留108行便于筛选。'],
  ['预览方式', '在 D:\\remotion_video 运行 npm run components，进入 http://127.0.0.1:3102。Studio 中 component-vertical 是原生竖版，component-horizontal 是横版对照。原有 Composition ID 保持不变。'],
  ['本地效果目录', `http://127.0.0.1:63204/ 或 out/components/index.html。187 个组件提供全分辨率原版三帧；${nativePortraitCount} 个已接入原生竖屏三帧；可切换画布视图、筛选组件库。`],
  ['复用入口', '相对路径以 D:\\remotion_video 为根目录。实际竖版、横版源码分别在 src/components/component-vertical、src/components/component-horizontal；entries/<slug>.tsx 是单组件演示入口，导出 Component、demo、meta。community 只保留注册、目录元数据和共享工具。'],
  ['已经验证', `Remotion ${verification.runtimeVersion}：${verification.registeredCount} 个注册项；${verification.count} 原版起始/中间/结束帧，${nativePortraitCount} 原生竖屏起始/中间/结束帧。108 原源码 SHA256 一致；全部 TypeScript 与接入层及竖屏代码 lint 通过。渲染抽样不等于任意长文案均已排版验证。`],
  ['竖屏适配', '竖版统一 1080×1920 / 30fps，面向 TikTok/抖音/快手；源码按竖屏重排，ID 为 Vertical- 加原 Composition。横版沿用来源规格，聊天示例使用1280×720。换文案后检查排版。'],
  ['示例数据', '图表数据、对话内容与界面 SVG 都是演示，不是实测模型排行或真实产品操作证据。'],
  ['字体与字幕', 'PromptZoom 恢复官方英文 props、90 帧和离线 Inter / Source Serif 4；部分组件及中文仍回退系统字体。原44个演示修改过文案/素材，并非像素一比一。生产字幕需实际配音时间戳。'],
  ['上游默认素材', 'Talkcraft 原图、视频与AI示例主持人按作者 HTML 注入并保存来源；其它库部分仍用示例 SVG。主持人可选，手部素材独立许可未核实；网站音效不在原 TSX 中。'],
  ['来源与许可', '每个库固定上游 commit，证据保存在 licenses/community。RVE / Bits 的 MIT 来自上游声明，未伪造其缺失的 LICENSE。Remotion 核心许可仍单独适用。'],
  ['video-talkcraft', '已按用户声明的非商业个人用途复制108原卡；保留 PolyForm Noncommercial 和来源。不安装整个工作台。原卡字节一致，Windows字体、网站HTML/MP4、音效仍可能与本地预览不同。'],
  ['研究日期', '2026-10-02。源码、预览、许可与版本按这次核对记录；以后更新需重新核对。'],
];
const componentRows = components.map((component) => [
  `${component.library} / ${component.name}`,
  component.verticalEntryPath,
  component.horizontalEntryPath,
  component.description,
  component.useCase,
]);
const sheetDefinitions = [
  {name: '组件目录', columns: ['组件名称','竖版相对文件路径','横版相对文件路径','适合表达的内容','适用场景'],
    data: componentRows, numeric: []},
  {name: '仓库说明', columns: ['仓库','定位','本次目录数量','本次导入数量','许可','接入方式','固定版本','GitHub','演示入口'],
    data: repositories.map((r) => [r.key === 'video-talkcraft' ? 'video-talkcraft' : r.name,r.kind,r.count,r.count,r.license,r.method,r.commit,`https://github.com/${r.repo}`,r.preview]), numeric: ['本次目录数量','本次导入数量']},
  {name: 'video-talkcraft', columns: ['组件名称','竖版相对文件路径','横版相对文件路径','适合表达的内容','适用场景'],
    data: components.filter((component) => component.library === 'Talkcraft').map((component) => [
      `${component.library} / ${component.name}`,
      component.verticalEntryPath,
      component.horizontalEntryPath,
      component.description,
      component.useCase,
    ]), numeric: []},
  {name: '使用说明', columns: ['事项','说明'], data: intro, numeric: []},
];
const sheets = sheetDefinitions.map(({numeric, ...sheet}) => ({...sheet, header: true,
  dtypes: Object.fromEntries(sheet.columns.map((c) => [c, numeric.includes(c) ? 'float64' : 'object'])),
  formats: Object.fromEntries(numeric.map((c) => [c,c === '演示秒数' ? '0.0' : '0'])),
}));
const colName = (index) => {let name = ''; for (let n=index+1;n>0;n=Math.floor((n-1)/26)) name=String.fromCharCode(65+(n-1)%26)+name; return name;};
const textWidth = (value) => Array.from(String(value ?? '')).reduce((sum,c) => sum + (c.charCodeAt(0)>255 ? 2 : 1), 0);
const styles = sheetDefinitions.map((sheet) => {
  const lastCol = colName(sheet.columns.length-1);
  const lastRow = sheet.data.length+1;
  const cellStyles = [{range:`A1:${lastCol}${lastRow}`,font_size:11,vertical_alignment:'middle',horizontal_alignment:'left',word_wrap:'auto-wrap'},
    {range:`A1:${lastCol}1`,font_weight:'bold',background_color:'#1E3A5F',font_color:'#FFFFFF',horizontal_alignment:'center'}];
  for (let row=3;row<=lastRow;row+=2) cellStyles.push({range:`A${row}:${lastCol}${row}`,background_color:'#EBF1F8'});
  sheet.columns.forEach((name,i) => {if (sheet.numeric.includes(name)) cellStyles.push({range:`${colName(i)}2:${colName(i)}${lastRow}`,horizontal_alignment:'right'});});
  return {name:sheet.name,cell_styles:cellStyles,
    col_sizes:sheet.columns.map((column,i) => ({range:`${colName(i)}:${colName(i)}`,type:'pixel',size:Math.min(400,Math.max(90,Math.max(textWidth(column),...sheet.data.map((r)=>textWidth(r[i])))*8+20))})),
    row_sizes:[{range:'1:1',type:'pixel',size:42},{range:`2:${lastRow}`,type:'auto'}],
  };
});
await writeFile(path.join(root,'.runtime/component-workbook.json'),JSON.stringify({sheets},null,2));
await writeFile(path.join(root,'.runtime/component-path-workbook.json'),JSON.stringify({sheets},null,2));
await writeFile(path.join(root,'.runtime/component-workbook-styles.json'),JSON.stringify({styles},null,2));

const escape = (text) => String(text).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const cards = components.map((c) => {
  const frames = c.verification.images.map((src, i) =>
    `<figure><img loading="lazy" src="${escape(src)}" alt="${escape(c.name)} 第 ${c.verification.frames[i]} 帧"><figcaption>第 ${c.verification.frames[i]} 帧</figcaption></figure>`
  ).join('');
  const portrait = c.portraitVerification
    ? `<div class="portrait"><img loading="lazy" src="${escape(c.portraitVerification.previewImage)}" alt="${escape(c.name)} 原生竖屏预览"><p>1080×1920 · 30fps · 原生竖屏</p></div>`
    : '<div class="portrait empty">原生竖屏待接入；先看原版三帧。</div>';
  const portraitLink = c.portraitVerification
    ? `<a href="http://127.0.0.1:3102/Vertical-${encodeURIComponent(c.compositionId)}" target="_blank">播放原生竖屏</a>`
    : '';
  return `<article data-library="${escape(c.library)}" data-search="${escape(`${c.name} ${c.effect} ${c.useCase}`)}"><h2>${escape(c.name)} <small>${escape(c.library)}</small></h2><p>${escape(c.effect)}</p><p class="muted">适合：${escape(c.useCase)}</p><div class="frames">${frames}</div>${portrait}<nav><a href="http://127.0.0.1:3102/${encodeURIComponent(c.compositionId)}" target="_blank">播放原版</a>${portraitLink}<a href="${escape(c.previewUrl)}" target="_blank" rel="noopener">作者演示</a><a href="${escape(c.sourceUrl)}" target="_blank" rel="noopener">固定版本源码</a></nav><p class="license">${escape(c.licenseNote)}</p></article>`;
}).join('\n');
await writeFile(path.join(root,'out/components/index.html'),`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Remotion 187 个组件目录</title><style>body{margin:0;background:#f1f5f9;color:#172033;font:16px/1.6 "Microsoft YaHei UI",Arial,sans-serif}main{max-width:1450px;margin:auto;padding:36px 24px}h1{margin:0;font-size:34px}header{margin-bottom:24px}input,select{padding:11px;border:1px solid #cbd5e1;border-radius:10px;font:inherit;margin:10px 10px 0 0}input{width:320px}.grid{display:grid;gap:20px}article{background:white;padding:24px;border-radius:16px;border:1px solid #e2e8f0}h2{margin:0;font-size:24px}small,.muted,.license,figcaption{color:#64748b}small{font-size:15px;margin-left:12px}.frames{display:flex;gap:12px}figure{width:33.33%;margin:0}img{display:block;width:100%;background:#e2e8f0;border-radius:8px}figcaption{font-size:13px}nav{display:flex;gap:22px;flex-wrap:wrap;margin-top:16px}a{color:#0369a1;text-decoration:none}.license{font-size:13px;margin-bottom:0}button{font:inherit}.portrait{display:none}.portrait img{max-width:320px;width:100%}.portrait p{color:#64748b;font-size:13px}.portrait.empty{padding:28px;border:1px dashed #cbd5e1;border-radius:12px;color:#64748b;background:#f8fafc}body[data-canvas="portrait"] .frames{display:none}body[data-canvas="portrait"] .portrait{display:block}@media(max-width:720px){.frames{flex-wrap:wrap}figure{width:100%}input{width:calc(100% - 24px)}}</style><body data-canvas="portrait"><main><header><h1>187 个现成 Remotion 组件</h1><p>187 个社区组件均提供原生竖屏布局，并在生产渲染层接入统一 native material path。连续动画需运行 <code>npm run components</code>。</p><p>未来成片为 1080×1920 / 30fps。竖屏版直接在竖屏画布上排版，原版保留作对照；新增文案、数据或素材仍须检查换行与遮挡。Talkcraft 原源码字节一致；官网 HTML、字体和音效不保证逐像素相同。数据、对话及人物是作者演示素材。</p><input id="search" placeholder="搜索组件、效果或场景" aria-label="搜索组件"><select id="library" aria-label="组件库"><option value="">全部组件库</option>${repositories.map((r)=>`<option>${escape(r.name)}</option>`).join('')}</select><select id="canvas" aria-label="画布预览"><option value="portrait">原生竖屏</option><option value="original">原版画布</option></select><p id="count">187 个组件</p></header><section class="grid">${cards}</section></main><script>const canvas=document.querySelector('#canvas');canvas.addEventListener('change',()=>{document.body.dataset.canvas=canvas.value;});const search=document.querySelector('#search'),library=document.querySelector('#library'),cards=[...document.querySelectorAll('article')];function filter(){let n=0;for(const card of cards){const visible=(!library.value||card.dataset.library===library.value)&&card.dataset.search.toLowerCase().includes(search.value.trim().toLowerCase());card.hidden=!visible;if(visible)n++;}document.querySelector('#count').textContent=n+' 个组件';}search.addEventListener('input',filter);library.addEventListener('change',filter);</script></html>`);
console.log('Built 187 component pairs and five-column workbook payload; 187-row catalogue and 108-row Talkcraft subset.');
