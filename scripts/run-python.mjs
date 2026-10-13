#!/usr/bin/env node
/* Run a Python script with the project venv on any platform. */

import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const candidates = [
  path.join(root, '.venv-videoagents', 'bin', 'python'),
  path.join(root, '.venv-videoagents', 'Scripts', 'python.exe'),
  path.join(root, '.venv', 'bin', 'python'),
  path.join(root, '.venv', 'Scripts', 'python.exe'),
];
const python = candidates.find((candidate) => fs.existsSync(candidate)) || 'python3';
const script = process.argv[2];
if (!script) {
  console.error('Usage: node scripts/run-python.mjs <script.py> [args...] | node scripts/run-python.mjs -m <module> [args...]');
  process.exit(1);
}
if (script.startsWith('-')) {
  // Module-style invocation, e.g. `-m pytest tests/ -q`.
  const result = spawnSync(python, process.argv.slice(2), {stdio: 'inherit'});
  process.exit(result.status ?? 1);
}
const result = spawnSync(python, [path.resolve(root, script), ...process.argv.slice(3)], {stdio: 'inherit'});
process.exit(result.status ?? 1);
