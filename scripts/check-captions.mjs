import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {captionPages} from '../src/components/captionPages.ts';

const episode = JSON.parse(readFileSync(new URL('../src/episode.generated.json', import.meta.url), 'utf8'));
const pages = captionPages(episode.captions);
assert(pages.length > 20, 'Chinese tokens must not collapse into one giant caption');
assert.equal(pages.map(p => p.text).join(''), episode.captions.map(c => c.text).join(''));
assert(pages.every(p => p.text.length <= 16));
assert(pages.every(p => Number.isFinite(p.durationMs) && p.durationMs > 0));
assert(pages.every(p => p.durationMs <= 1900));
for (let index = 1; index < pages.length; index++) {
  assert(pages[index - 1].startMs + pages[index - 1].durationMs <= pages[index].startMs);
}
assert.deepEqual(captionPages([]), []);
console.log(`Chinese caption pagination checked: ${pages.length} pages, max ${Math.max(...pages.map(p => p.text.length))} characters`);
