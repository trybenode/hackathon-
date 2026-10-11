/* eslint-disable @typescript-eslint/no-require-imports -- This test uses a CommonJS TypeScript loader without adding a test runtime dependency. */
/** Checks locale copy/fallback and ensures presentation translation cannot change wire or React identity attributes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
require.extensions['.ts'] = function load(module, filename) {
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, filename);
};
const { workerCopy } = require('../src/lib/workerLanguage.ts');
const { formatNaira, formatFullDate } = require('../src/lib/workerFormat.ts');
for (const language of ['yo', 'ha', 'ig']) {
  for (const phrase of ['Home', 'Jobs', 'Profile', 'Create Job', 'Import Record', 'Listen', 'Confirm Completion', 'Job status', 'Payment status', 'Sandbox check · demo']) {
    assert.notEqual(workerCopy(language, phrase), phrase, `${language}: ${phrase}`);
  }
  assert.equal(workerCopy(language, 'Customer-provided job name'), 'Customer-provided job name');
  assert.match(formatNaira(25000, language), /25/);
  assert.ok(formatFullDate('2026-10-10T12:00:00Z', language));
}
assert.equal(workerCopy('en', 'Create Job'), 'Create Job');
function inspect(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) { inspect(filename); continue; }
    if (!filename.endsWith('.tsx')) continue;
    const sf = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    function scan(node) {
      if (ts.isCallExpression(node) && node.expression.getText(sf) === 'w') {
        let parent = node.parent;
        while (parent && !ts.isJsxExpression(parent) && !ts.isJsxElement(parent)) parent = parent.parent;
        if (parent && ts.isJsxExpression(parent) && ts.isJsxAttribute(parent.parent)) {
          assert.ok(!['key', 'value', 'type', 'status', 'className', 'aria-current', 'id', 'name'].includes(parent.parent.name.getText(sf)), `${filename}: translated domain/identity attribute`);
        }
      }
      ts.forEachChild(node, scan);
    }
    scan(sf);
  }
}
inspect(path.join(__dirname, '../src/app/worker'));
inspect(path.join(__dirname, '../src/components/worker'));
console.log('Worker language, formatting and presentation-boundary checks passed.');
