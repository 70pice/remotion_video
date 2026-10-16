import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import process from 'node:process';
import test from 'node:test';
import {ffmpegExecutable, ffprobeExecutable} from '../../scripts/render-timeline.mjs';

for (const [name, resolve] of [['ffmpeg', ffmpegExecutable], ['ffprobe', ffprobeExecutable]]) {
  test(`Windows ${name} probe executes a real executable without POSIX execute bits`,
    {skip: process.platform !== 'win32'}, async () => {
      const executable = await resolve();
      const stat = await fs.stat(executable);
      assert.ok(stat.isFile());
      assert.match(executable, /\.exe$/i);
      assert.equal(stat.mode & 0o111, 0);
    });
}
