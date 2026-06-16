import { readFileSync } from 'fs';

const html = readFileSync('bot-dashboard/index.html', 'utf8');
const sIdx = html.indexOf('<script>') + 8;
const eIdx = html.lastIndexOf('</script>');
const js = html.slice(sIdx, eIdx);

// Count backticks - should be even for valid template literals
const backtickCount = (js.match(/`/g) || []).length;
console.log(`Backtick count: ${backtickCount} (should be even)`);
if (backtickCount % 2 !== 0) console.log('❌ UNEVEN BACKTICKS!');

// Count braces
let braceCount = 0;
let minBrace = 0;
for (let i = 0; i < js.length; i++) {
  if (js[i] === '{') braceCount++;
  if (js[i] === '}') braceCount--;
  minBrace = Math.min(minBrace, braceCount);
}
console.log(`Brace balance: ${braceCount} (should be 0), min depth: ${minBrace}`);

// Check for template literal issues - the big innerHTML template
const tlStart = js.indexOf('`<header');
const tlEnd = js.indexOf('`;\nconst INTEGRATIONS');
if (tlStart > 0 && tlEnd > 0) {
  const tl = js.slice(tlStart, tlEnd + 1);
  console.log(`Template literal: ${tl.length} chars from ${tlStart} to ${tlEnd}`);
  // Count backticks IN the template literal
  const tlBackticks = (tl.match(/`/g) || []).length;
  console.log(`  Backticks in TL: ${tlBackticks} (should be 1 for opening, ${tl[tl.length-1] === '`' ? 'found closing' : 'missing closing'})`);
}

// Check for any ${...} interpolation that might be malformed
const tlContent = js.slice(tlStart, tlEnd);
// Find all ${...} expressions
let depth = 0;
let inExpr = false;
let exprStart = 0;
for (let i = 0; i < tlContent.length; i++) {
  const c = tlContent[i];
  if (c === '$' && i+1 < tlContent.length && tlContent[i+1] === '{') {
    if (depth === 0 && !inExpr) {
      inExpr = true;
      exprStart = i;
      depth = 1;
    }
    i++;
  } else if (c === '{' && inExpr) {
    depth++;
  } else if (c === '}' && inExpr) {
    depth--;
    if (depth === 0) {
      inExpr = false;
    }
  }
}
console.log(`Unclosed ${} expressions: ${inExpr ? 'YES at position ' + exprStart : 'NONE'}`);

// Wrap the full JS and test
try {
  new Function(js);
  console.log('✅ new Function(): PASSED');
} catch(e) {
  console.log(`❌ new Function(): ${e.message.slice(0, 100)}`);
}

// Test a simpler approach - wrap in async function
try {
  const wrapped = 'async function test() {\n' + js + '\n}';
  new Function(wrapped);
  console.log('✅ Wrapped in async function: PASSED');
} catch(e) {
  console.log(`❌ Wrapped: ${e.message.slice(0, 100)}`);
}