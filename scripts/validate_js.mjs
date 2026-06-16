import { readFileSync, writeFileSync } from 'fs';

const html = readFileSync('bot-dashboard/index.html', 'utf8');
const sIdx = html.indexOf('<script>');
const eIdx = html.indexOf('</script>', sIdx + 1);
const js = html.slice(sIdx + 8, eIdx);

console.log('JS length:', js.length);

// Test 1: Function constructor (browser-like)
try {
  const fn = new Function(js);
  console.log('✅ new Function(): PASSED');
} catch(e) {
  console.log('❌ new Function():', e.message);
  // Show context near error position (position 2 since that's where it chokes)
  if (e.message.includes('Missing initializer')) {
    // Try removing CR chars
    const cleaned = js.replace(/\r/g, '\n');
    try {
      new Function(cleaned);
      console.log('✅ After CR->LF fix: PASSED');
    } catch(e2) {
      console.log('❌ After CR->LF fix:', e2.message);
    }
  }
}

// Test 2: Check for any hidden characters between script tags
let suspicious = false;
for (let i = 0; i < js.length; i++) {
  const c = js.charCodeAt(i);
  if (c !== 13 && c !== 10 && c !== 32 && c !== 9 && (c < 32 || c > 126)) {
    // Em dash (151), smart quotes (147, 148), etc are OK in JS strings
    if (![147,148,151,8211,8212,8216,8217,8220,8221,8226,8230].includes(c)) {
      console.log('Suspicious char at', i, ': code', c, 'hex', c.toString(16));
      suspicious = true;
    }
  }
}
if (!suspicious) console.log('✅ No suspicious characters found');

// Test 3: Check if it's a new Function() issue with the em-dash characters
// Try with a simple eval-like approach
try {
  const result = (1, eval)(js);
  console.log('✅ eval(): PASSED');
} catch(e) {
  console.log('❌ eval():', e.message.slice(0, 80));
}