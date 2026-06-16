import { readFileSync, writeFileSync } from 'fs';

const html = readFileSync('bot-dashboard/index.html', 'utf8');
const sIdx = html.indexOf('<script>') + 8;
const eIdx = html.lastIndexOf('</script>');
const jsStr = html.slice(sIdx, eIdx);

console.log(`JS string length: ${jsStr.length}`);

// Wrap in a function body and test syntax
try {
  const fn = new Function(jsStr);
  console.log('✅ new Function() PASSED — HTML is already valid');
} catch(e) {
  console.log(`❌ new Function() FAILED: ${e.message}`);
}

// Specifically look for the exact byte causing "Missing initializer"
// Write a simple test file
let testJs = jsStr.replace(/\r/g, '');  // Remove CR
writeFileSync('_test_parse.js', testJs);
console.log(`Wrote _test_parse.js (${testJs.length} bytes)`);