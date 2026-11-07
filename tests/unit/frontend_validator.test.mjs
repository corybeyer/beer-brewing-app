import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { analyze } from '../../scripts/validation/frontend.mjs';

const policy = JSON.parse(readFileSync(new URL('../../scripts/validation/policy.json', import.meta.url)));
const manifest = (name, extra) => JSON.stringify({ name, ...extra });
function fixture(extra = {}) {
  return {
    'package.json': manifest('root', { workspaces: ['apps/web', 'packages/ui', 'packages/design-system', 'packages/communications'], devDependencies: { '@playwright/test': '*' } }),
    'apps/web/package.json': manifest('@brewery/web', { dependencies: { react: '*', '@brewery/ui': '*', '@brewery/design-system': '*', '@brewery/communications': '*' } }),
    'packages/ui/package.json': manifest('@brewery/ui', { dependencies: { '@brewery/design-system': '*' }, peerDependencies: { react: '*' }, exports: { '.': './src/index.tsx', './styles.css': './src/components.css' } }),
    'packages/design-system/package.json': manifest('@brewery/design-system', { dependencies: { 'lucide-react': '*' }, exports: { './icons': './src/Icon.tsx', './styles.css': './src/styles.css' } }),
    'packages/communications/package.json': manifest('@brewery/communications', { exports: { '.': './src/readiness.ts' } }),
    'packages/ui/src/index.tsx': '',
    'packages/ui/src/components.css': '',
    'packages/design-system/src/Icon.tsx': '',
    'packages/design-system/src/styles.css': '',
    'packages/communications/src/readiness.ts': '',
    'packages/design-system/src/tokens/tokens.css': ':root { --color-text: #172b40; --space-4: 1rem; }',
    ...extra,
  };
}
const rules = (files) => analyze(fixture(files), policy).map((item) => item.rule);

test('public exports, type imports, and layout tokens pass', () => {
  assert.deepEqual(rules({
    'apps/web/src/view.tsx': "import { Button } from '@brewery/ui'; // <button style={{color:'red'}} />\nexport const View = () => <Button>Save</Button>;",
    'apps/web/src/features/recipes/layout.css': '/* color: red */ .layout { display: grid; gap: var(--space-4); }',
  }), []);
});

test('static, type, export, dynamic, and require imports respect boundaries', () => {
  for (const code of ["import type { X } from '@brewery/ui';", "export { X } from '@brewery/ui';", "import('@brewery/ui');", "require('@brewery/ui');"]) {
    assert.ok(rules({ 'packages/design-system/src/bad.ts': code }).includes('js.dependency'));
  }
  assert.ok(rules({ 'apps/web/src/view.ts': 'import(moduleName)' }).includes('js.dynamic'));
});

test('relative private imports and unpublished package subpaths fail', () => {
  assert.ok(rules({ 'apps/web/src/view.ts': "import '../../../packages/ui/src/index';" }).includes('js.private-import'));
  assert.ok(rules({ 'apps/web/src/view.ts': "import '@brewery/ui/src/index';" }).includes('manifest.exports'));
  assert.ok(rules({ 'apps/web/src/view.ts': "import 'axios';" }).includes('js.undeclared'));
});

test('visual presentation and controls cannot be recreated in screens', () => {
  for (const [code, expected] of [
    ['const V=()=> <div style={{color:"red"}} />', 'js.inline-style'],
    ['const V=()=> <Box sx={{color:"red"}} />', 'js.inline-style'],
    ['const V=()=> <button>Save</button>', 'js.native-control'],
    ['const V=()=> <div role="button">Save</div>', 'js.native-control'],
    ['const V=()=> <svg><path d="M0 0" /></svg>', 'js.svg'],
    ['fetch("/api/v1/readiness")', 'js.transport'],
    ['const url=import.meta.env.API_URL', 'js.configuration'],
  ]) assert.ok(rules({ 'apps/web/src/features/view.tsx': code }).includes(expected));
  assert.ok(!rules({ 'packages/ui/src/widget.tsx': 'export const Button=()=> <button>Save</button>' }).includes('js.native-control'));
  assert.ok(rules({ 'packages/ui/src/widget.tsx': 'const color="#ff0000";' }).includes('js.literal'));
});

test('CSS declarations are parsed and shared tokens/breakpoints are enforced', () => {
  for (const [css, expected] of [
    ['.x { color: red }', 'css.feature'],
    ['.x { color: #ffffff }', 'css.literal'],
    ['.x { margin: 12px }', 'css.literal'],
    ['.x { gap: var(--missing) }', 'css.token'],
    ['.x { --color-local: red }', 'css.token'],
    ['@media (max-width: 719px) { .x { display: block } }', 'css.breakpoint'],
    ['@import "https://fonts.example/font.css";', 'css.import'],
  ]) assert.ok(rules({ 'apps/web/src/features/recipes/style.css': css }).includes(expected));
  assert.ok(rules({ 'packages/ui/src/widget.css': '.x { color: var(--color-text, red) }' }).includes('css.literal'));
});

test('workspace cycles and forbidden declared dependencies fail', () => {
  const files = fixture({
    'packages/design-system/package.json': manifest('@brewery/design-system', { dependencies: { '@brewery/ui': '*' } }),
  });
  const results = analyze(files, policy);
  assert.ok(results.some((item) => item.rule === 'manifest.cycle'));
  assert.ok(results.some((item) => item.rule === 'manifest.dependencies'));
});

test('missing manifests, undeclared workspaces, and nonexistent exports fail', () => {
  assert.ok(rules({ 'packages/ui/package.json': manifest('wrong-name', {}) }).includes('manifest.dependencies'));
  assert.ok(rules({ 'package.json': manifest('root', { workspaces: [] }) }).includes('manifest.dependencies'));
  assert.ok(rules({ 'packages/ui/package.json': manifest('@brewery/ui', { exports: { '.': './missing.tsx' } }) }).includes('manifest.exports'));
});

test('malformed syntax fails closed and comments do not produce false violations', () => {
  assert.ok(rules({ 'apps/web/src/bad.tsx': 'const broken = <;' }).includes('js.syntax'));
  assert.ok(rules({ 'packages/ui/src/bad.css': '.bad {' }).includes('css.syntax'));
  assert.deepEqual(rules({ 'apps/web/src/comments.ts': '// import x from "sqlalchemy";\nconst message="<button style=red>";' }), []);
});
