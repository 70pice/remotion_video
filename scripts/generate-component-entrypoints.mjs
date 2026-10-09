import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const expectedPresetCount = 187;
const libraries = [
  {key:'snapcn', name:'Snapcn'}, {key:'rve', name:'RVE'},
  {key:'remocn', name:'Remocn'}, {key:'remotion-ui', name:'RemotionUI'},
  {key:'bits', name:'Bits'}, {key:'rendercomp', name:'RenderComp'},
  {key:'video-talkcraft', name:'Talkcraft'},
];
const componentPaths = [];
for (const library of libraries) {
  const components = JSON.parse(await readFile(path.join(root, 'src/components/community', `catalog-${library.key}.json`), 'utf8'));
  const verticalExports = [];
  for (const component of components) {
    const horizontalPath = `src/components/component-horizontal/${library.key}/entries/${component.slug}.tsx`;
    const verticalPath = `src/components/component-vertical/${library.key}/entries/${component.slug}.tsx`;
    for (const [orientation, file] of [['horizontal', horizontalPath], ['vertical', verticalPath]]) {
      const collection = orientation === 'horizontal' ? 'componentDemos' : 'nativeDemos';
      const imports = orientation === 'vertical' && library.key === 'video-talkcraft'
        ? `import {nativeDemos as groupA} from '../group-a';\nimport {nativeDemos as groupB} from '../group-b';\nimport {nativeDemos as groupC} from '../group-c';\nimport {nativeDemos as groupD} from '../group-d';\nconst nativeDemos = [...groupA, ...groupB, ...groupC, ...groupD];`
        : `import {${collection}} from '../demo';`;
      await mkdir(path.dirname(path.join(root,file)), {recursive:true});
      await writeFile(path.join(root,file), `${imports}

const found = ${collection}.find((item) => item.id === '${component.compositionId}');
if (!found) throw new Error('Missing component entry: ${component.compositionId}');

// Ready-to-preview component using the library's existing example props.
export const demo = found;
export const Component = found.component;
export const meta = {
  width: found.width, height: found.height,
  fps: found.fps, durationInFrames: found.durationInFrames,
};
export default Component;
`);
    }
    const exportName = component.slug.split('-').map((part) => part[0].toUpperCase() + part.slice(1)).join('');
    verticalExports.push(`export {default as ${exportName}} from './entries/${component.slug}';`);
    componentPaths.push({compositionId:component.compositionId, name:`${library.name} / ${component.name}`, library:library.name,
      verticalPath, horizontalPath,
      verticalSourcePath: library.key === 'video-talkcraft'
        ? `src/components/component-vertical/${library.key}/${component.slug}.tsx`
        : `src/components/component-vertical/${library.key}/demo.tsx`,
      horizontalSourcePath:component.localPath,
    });
  }
  await writeFile(path.join(root, 'src/components/component-vertical', library.key, 'index.ts'), verticalExports.join('\n') + '\n');
}
if (componentPaths.length !== expectedPresetCount || new Set(componentPaths.map((component) => component.compositionId)).size !== expectedPresetCount) throw new Error(`Expected ${expectedPresetCount} unique component pairs`);
for (const orientation of ['horizontal','vertical']) {
  await writeFile(path.join(root, 'src/components', `component-${orientation}`, 'index.ts'), libraries.map((library) =>
    `export * as ${library.name === 'Talkcraft' ? 'VideoTalkcraft' : library.name} from './${library.key}';`).join('\n') + '\n');
}
await writeFile(path.join(root, 'docs/component-paths.json'), JSON.stringify({components:componentPaths}, null, 2));
console.log(JSON.stringify({horizontal:expectedPresetCount, vertical:expectedPresetCount, pathPairs:componentPaths.length}));
