import {copyFile, mkdir, readFile, readdir, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {execFileSync} from 'node:child_process';

const root = process.cwd();
const upstream = process.argv[2];
if (!upstream) throw new Error('Pass the checked-out video-talkcraft repository path.');
const research = JSON.parse(await readFile(path.join(root, 'docs/video-talkcraft-catalog.json'), 'utf8'));
const revision = execFileSync('git', ['-C', upstream, 'rev-parse', 'HEAD'], {encoding: 'utf8'}).trim();
const sourceChanges = execFileSync('git', ['-C', upstream, 'status', '--porcelain', '--', 'template/cards'], {encoding: 'utf8'}).trim();
if (revision !== research.commit || sourceChanges) throw new Error('Upstream must be the pinned commit with unchanged template/cards.');
const destination = path.join(root, 'src/components/component-horizontal/video-talkcraft');
const licenseDir = path.join(root, 'licenses/community/video-talkcraft');
await mkdir(path.join(destination, 'cards'), {recursive: true});
await mkdir(licenseDir, {recursive: true});
const files = (await readdir(path.join(upstream, 'template/cards'))).filter((f) => f.endsWith('.tsx')).sort();
if (files.length !== 108 || research.components.length !== 108) throw new Error('Expected 108 original cards.');
const manifest = [];
const imports = [];
const demos = [];
const exports = [];
const catalogue = [];
for (const [index, card] of research.components.entries()) {
  const filename = `${card.slug}.tsx`;
  if (!files.includes(filename)) throw new Error(`Missing upstream card: ${filename}`);
  const source = path.join(upstream, 'template/cards', filename);
  const target = path.join(destination, 'cards', filename);
  await copyFile(source, target);
  const sha256 = createHash('sha256').update(await readFile(source)).digest('hex');
  manifest.push({slug: card.slug, sourcePath: card.sourcePath, localPath: path.relative(root, target).replaceAll('\\', '/'), sha256});
  const symbol = card.slug.split('-').map((p) => p[0].toUpperCase() + p.slice(1)).join('');
  imports.push(`import * as Card${index} from './cards/${card.slug}';`);
  exports.push(`export {default as ${symbol}} from './cards/${card.slug}';`);
  demos.push(`  {id: 'Talkcraft-${card.slug}', name: ${JSON.stringify(card.name)}, slug: '${card.slug}', component: function CardDemo${index}() {return <IsolatedCard><Card${index}.default {...originalPreviewPropsAtFrame('${card.slug}', useCurrentFrame())} /></IsolatedCard>;}, ...Card${index}.meta},`);
  catalogue.push({slug: card.slug, name: card.name, effect: card.effect, useCase: card.usecase,
    sourcePath: card.sourcePath, previewUrl: card.preview, localPath: manifest.at(-1).localPath,
    compositionId: `Talkcraft-${card.slug}`, licenseNote: 'PolyForm Noncommercial 1.0.0；按用户声明非商业用途导入；原源码字节保持一致，演示素材另记来源'});
  card.integrationStatus = '已导入原源码；非商业用途；验证待完成';
  card.localPath = manifest.at(-1).localPath;
  card.compositionId = `Talkcraft-${card.slug}`;
}
await writeFile(path.join(destination, 'index.ts'), exports.join('\n') + '\n');
await writeFile(path.join(destination, 'demo.tsx'), `import {useCurrentFrame} from 'remotion';\nimport {IsolatedCard} from '../../community/IsolatedCard';\nimport {originalPreviewPropsAtFrame} from './preview-props';\n${imports.join('\n')}\n\n// Original meta is evaluated by Remotion; no guessed dimensions or durations.\nexport const componentDemos = [\n${demos.join('\n')}\n];\n`);
await writeFile(path.join(root, 'src/components/community/catalog-video-talkcraft.json'), JSON.stringify(catalogue, null, 2));
await writeFile(path.join(licenseDir, 'source-manifest.json'), JSON.stringify({repository: research.repository, commit: research.commit, count: manifest.length, files: manifest}, null, 2));
for (const [source, target] of [['LICENSE', 'LICENSE'], ['README.md', 'UPSTREAM-README.md'], ['template/README.md', 'UPSTREAM-TEMPLATE-README.md']]) {
  await copyFile(path.join(upstream, source), path.join(licenseDir, target));
}
await writeFile(path.join(licenseDir, 'IMPORT.md'), `# video-talkcraft import\n\nPinned commit: ${research.commit}.\n\n108 template/cards TSX files copied byte for byte. source-manifest.json records SHA256 for each card. Original standalone defaults and metadata are preserved. demo.tsx supplies published author assets via preview-props.ts and isolates global CSS in a ShadowRoot; the card source is unchanged.\n\nUse: user-declared noncommercial personal short videos. PolyForm Noncommercial 1.0.0 retained. Media attribution and unresolved asset provenance are recorded separately. Website HTML/MP4 demos are a different implementation and may include sounds absent from original TSX. Source equality is not a pixel-identical website or audio claim.\n\nOriginal cards are vendored and excluded from first-party ESLint style rules. Strict TypeScript and frame render checks cover all imported cards.\n`);
research.integration = {count: 108, usage: 'user-declared noncommercial personal short videos', sourceEquality: 'SHA256 manifest for byte-preserved source', checkedAt: new Date().toISOString()};
await writeFile(path.join(root, 'docs/video-talkcraft-catalog.json'), JSON.stringify(research, null, 2));
console.log('Copied 108 unchanged cards, source hashes, metadata previews and license evidence.');
