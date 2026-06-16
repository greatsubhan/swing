import { readFileSync, writeFileSync } from 'fs';

const file = process.argv[2] || 'bot-dashboard/index.html';
const html = readFileSync(file, 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('FAIL: No <script> block found'); process.exit(1); }

const js = m[1];
let exitCode = 0;

// SYNTAX CHECK
try {
  new Function(js);
  console.log('✓ Syntax check passed');
} catch (e) {
  console.error('✗ Syntax error:', e.message);
  exitCode = 1;
}

// LINT - check common patterns
if (js.includes('}]}}};')) {
  console.error('✗ Found extra closing braces pattern: }]}}}');
  exitCode = 1;
}

// LINT - check template literal nesting
let backtickCount = 0;
for (let i = 0; i < js.length; i++) {
  if (js[i] === '`') backtickCount++;
  // Check that ${} inside backticks are balanced
}
if (backtickCount % 2 !== 0) {
  console.error(`✗ Unbalanced backticks: ${backtickCount} found (expected even)`);
  exitCode = 1;
}

// LINT - brace depth
let depth = 0;
let inStr = false, strChar = '';
let inTmpl = false, inBlock = false;
for (let i = 0; i < js.length; i++) {
  const c = js[i];
  if (inBlock) { if (c === '*' && js[i+1] === '/') { inBlock = false; i++; } continue; }
  if (inStr) { if (c === '\\') i++; else if (c === strChar) inStr = false; continue; }
  if (c === '/' && js[i+1] === '*') { inBlock = true; i++; continue; }
  if (c === "'" || c === '"') { inStr = true; strChar = c; continue; }
  if (c === '`') { inTmpl = !inTmpl; continue; }
  if (c === '{' || c === '(' || c === '[') depth++;
  if (c === '}' || c === ')' || c === ']') {
    depth--;
    if (depth < 0) {
      const ctx = js.substring(Math.max(0, i - 40), Math.min(js.length, i + 10));
      console.error(`✗ Brace underflow at position ${i}: "${ctx}"`);
      exitCode = 1;
      break;
    }
  }
}

if (depth !== 0) {
  console.error(`✗ Final brace depth is ${depth} (expected 0)`);
  exitCode = 1;
}

if (exitCode === 0) {
  console.log('✓ All validation checks passed');
} else {
  process.exit(exitCode);
}