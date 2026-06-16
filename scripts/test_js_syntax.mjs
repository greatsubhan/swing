import { readFileSync, writeFileSync } from 'fs';

const html = readFileSync('bot-dashboard/index.html', 'utf8');
const start = html.indexOf('<script>') + 8;
const end = html.indexOf('</script>');
const js = html.slice(start, end);

console.log(`JS extracted: ${js.length} chars`);

// Test with Function constructor (closest to browser behavior)
try {
  // Wrap in a function to make it a valid expression (script-level code works in Function body)
  new Function(js);
  console.log('✅ FUNCTION CONSTRUCTOR: PASSED - JS syntax is valid');
} catch(e) {
  console.log('❌ FUNCTION CONSTRUCTOR FAILED:', e.message);
}

// Test individual parts
// Check MAP object
try {
  const mapEnd = js.indexOf('reviews:{');
  const mapPart = js.slice(0, js.indexOf('reviews:{')) + 'dummy:1});';
  // Actually just try parsing the whole file differently 
  console.log('Review data is at position:', js.indexOf('reviews:'));
} catch(e) {
  console.log('Parse test error:', e.message);
}