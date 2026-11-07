/** Parse source, never execute it. Findings contain locations/rules, not source values. */
import { parse } from '@babel/parser';
import postcss from 'postcss';
import { posix, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';

function ownerOf(path, policy) {
  return Object.entries(policy.owners).find(([, rule]) => path === rule.root || path.startsWith(`${rule.root}/`))?.[0];
}
function walk(node, visit) {
  if (!node || typeof node !== 'object') return;
  if (typeof node.type === 'string') visit(node);
  for (const [key, value] of Object.entries(node)) {
    if (['loc', 'comments', 'tokens', 'extra'].includes(key)) continue;
    if (Array.isArray(value)) value.forEach((child) => walk(child, visit));
    else if (value && typeof value === 'object') walk(value, visit);
  }
}
const packageName = (specifier) => specifier.startsWith('@') ? specifier.split('/').slice(0, 2).join('/') : specifier.split('/')[0];
const permits = (owner, dependency, policy) => owner === dependency || policy.owners[owner]?.uses.some((item) => item === '*' || item === dependency);

export function analyze(files, policy) {
  const findings = [];
  const add = (rule, path, message, line = 1) => findings.push({ rule, path, line, message });
  const manifests = {};
  for (const [path, source] of Object.entries(files)) {
    if (!path.endsWith('package.json')) continue;
    try { manifests[path] = JSON.parse(source); }
    catch { add('syntax.json', path, 'Package manifest does not parse.'); }
  }
  const byName = Object.fromEntries(Object.entries(manifests).filter(([, m]) => m.name).map(([path, m]) => [m.name, { path, manifest: m }]));
  const rootManifest = manifests['package.json'] ?? {};
  for (const [name, owner] of Object.entries(policy.node_packages)) {
    const root = policy.owners[owner].root;
    if (manifests[`${root}/package.json`]?.name !== name) add('manifest.dependencies', `${root}/package.json`, 'Workspace manifest must exist and match its approved package name.');
    if (!(rootManifest.workspaces ?? []).includes(root)) add('manifest.dependencies', 'package.json', 'Approved browser package is missing from the root workspaces.');
  }
  for (const [path, manifest] of Object.entries(manifests)) {
    if (!manifest.exports || typeof manifest.exports !== 'object') continue;
    for (const target of Object.values(manifest.exports)) {
      if (typeof target !== 'string' || !/\.(tsx?|jsx?|css)$/.test(target)) continue;
      const resolved = posix.normalize(posix.join(posix.dirname(path), target));
      if (!target.startsWith('./') || !resolved.startsWith(posix.dirname(path) + '/') || !(resolved in files)) add('manifest.exports', path, 'Public export target must exist inside its owning package.');
    }
  }
  const dependencies = (manifest, dev) => ({ ...manifest.dependencies, ...manifest.peerDependencies, ...(dev ? manifest.devDependencies : {}) });
  const tokens = new Set();
  for (const path of policy.token_files) {
    if (!files[path]) continue;
    try { postcss.parse(files[path]).walkDecls((decl) => { if (decl.prop.startsWith('--')) tokens.add(decl.prop); }); }
    catch { add('css.syntax', path, 'Token stylesheet does not parse.'); }
  }

  function checkImport(path, specifier, line) {
    const owner = ownerOf(path, policy);
    if (!owner) return;
    const runtime = path.includes('/src/');
    const restricted = ['web', 'ui', 'design-system', 'communications', 'domain', 'validation'].includes(owner);
    if (specifier.startsWith('.')) {
      const target = posix.normalize(posix.join(posix.dirname(path), specifier));
      const targetOwner = ownerOf(target, policy);
      if (!permits(owner, targetOwner, policy) || restricted && targetOwner !== owner) {
        add('js.private-import', path, 'Cross-package imports must use named public exports.', line);
      }
      if (restricted && ![target, ...['.ts', '.tsx', '.js', '.jsx', '.css', '/index.ts', '/index.tsx'].map((extension) => target + extension)].some((name) => name in files)) {
        add('js.private-import', path, 'Relative import target is missing or outside published source.', line);
      }
      return;
    }
    if (specifier.startsWith('node:')) {
      if (runtime && ['web', 'ui', 'design-system', 'communications'].includes(owner)) add('js.dependency', path, 'Browser source cannot import Node runtime modules.', line);
      return;
    }
    const name = packageName(specifier);
    const target = policy.node_packages[name];
    const manifest = manifests[`${policy.owners[owner].root}/package.json`] ?? rootManifest;
    const declared = { ...dependencies(manifest, !runtime), ...(!runtime ? rootManifest.devDependencies : {}) };
    if (!(name in declared)) add('js.undeclared', path, 'Imported dependency must be declared by its consuming package.', line);
    if (target) {
      if (!permits(owner, target, policy)) add('js.dependency', path, `${owner} cannot depend on ${target}.`, line);
      const exports = byName[name]?.manifest.exports;
      const subpath = specifier === name ? '.' : '.' + specifier.slice(name.length);
      if (!exports || typeof exports === 'string' && subpath !== '.' || typeof exports === 'object' && !(subpath in exports)) {
        add('manifest.exports', path, 'Import bypasses the package public exports.', line);
      }
    } else if (runtime && restricted && !policy.owners[owner].node.includes(name)) {
      add('js.dependency', path, 'Runtime dependency is outside this owner’s approved boundary.', line);
    }
  }

  for (const [path, source] of Object.entries(files)) {
    const owner = ownerOf(path, policy);
    if (!owner) continue;
    if (/\.[cm]?[jt]sx?$/.test(path)) {
      let tree;
      try { tree = parse(source, { sourceType: 'unambiguous', plugins: ['typescript', 'jsx'], createImportExpressions: true }); }
      catch (error) { add('js.syntax', path, 'JavaScript/TypeScript source does not parse.', error.loc?.line ?? 1); continue; }
      const appSource = owner === 'web' && path.includes('/src/');
      walk(tree, (node) => {
        const line = node.loc?.start.line ?? 1;
        if (['web', 'ui', 'design-system'].includes(owner) && path.includes('/src/') && node.type === 'StringLiteral' && /^(#[0-9a-f]{3,8}|(?:rgb|rgba|hsl|hsla|oklch|oklab)\(.*\))$/i.test(node.value)) {
          add('js.literal', path, 'Define palette values in design-system tokens, not component source.', line);
        }
        if (['ImportDeclaration', 'ExportNamedDeclaration', 'ExportAllDeclaration'].includes(node.type) && node.source) checkImport(path, node.source.value, line);
        const dynamic = node.type === 'ImportExpression' ? node.source : node.type === 'CallExpression' && node.callee.type === 'Identifier' && node.callee.name === 'require' ? node.arguments[0] : null;
        if (dynamic) {
          if (dynamic.type === 'StringLiteral') checkImport(path, dynamic.value, line);
          else if (appSource || ['ui', 'design-system', 'communications'].includes(owner)) add('js.dynamic', path, 'Computed module imports need a reviewed exception.', line);
        }
        if (appSource && node.type === 'JSXAttribute' && ['style', 'sx', 'css', 'color', 'fill', 'stroke', 'fontSize', 'backgroundColor', 'dangerouslySetInnerHTML'].includes(node.name?.name)) {
          add('js.inline-style', path, 'Use shared component variants and semantic tokens instead of feature-local presentation.', line);
        }
        if (appSource && node.type === 'JSXOpeningElement' && node.name.type === 'JSXIdentifier') {
          if (['button', 'input', 'select', 'textarea'].includes(node.name.name)) add('js.native-control', path, 'Use a control from @brewery/ui.', line);
          if (['svg', 'path', 'rect', 'circle', 'ellipse', 'polygon', 'polyline'].includes(node.name.name)) add('js.svg', path, 'Own repeatable icons/charts in design-system or shared UI.', line);
          if (/^[a-z]/.test(node.name.name) && node.attributes.some((attribute) => attribute.type === 'JSXAttribute' && attribute.name?.name === 'role' && attribute.value?.value === 'button')) add('js.native-control', path, 'Use a library control rather than a screen-local button imitation.', line);
        }
        if (appSource && node.type === 'CallExpression' && (node.callee.name === 'fetch' || node.callee.type === 'MemberExpression' && ['window', 'globalThis'].includes(node.callee.object.name) && node.callee.property.name === 'fetch')) {
          add('js.transport', path, 'HTTP transport belongs in @brewery/communications, not individual screens.', line);
        }
        if (appSource && node.type === 'MemberExpression' && (node.object.type === 'MetaProperty' && node.property.name === 'env' || node.object.name === 'process' && node.property.name === 'env')) {
          add('js.configuration', path, 'Browser environment handling needs a central configuration adapter.', line);
        }
      });
    }
    if (path.endsWith('.css')) {
      let css;
      try { css = postcss.parse(source, { from: path }); }
      catch (error) { add('css.syntax', path, 'Stylesheet does not parse.', error.line ?? 1); continue; }
      const isTokenFile = policy.token_files.includes(path);
      const feature = path.startsWith('apps/web/src/features/');
      const layout = /^(display|position|inset(?:-.+)?|top|right|bottom|left|z-index|overflow(?:-.+)?|grid(?:-.+)?|flex(?:-.+)?|align-.+|justify-.+|place-.+|order|gap|row-gap|column-gap|margin(?:-.+)?|padding(?:-.+)?|(?:min-|max-)?(?:width|height))$/;
      css.walkDecls((decl) => {
        const prop = decl.prop.toLowerCase();
        const line = decl.source?.start?.line ?? 1;
        if (prop.startsWith('--') && !isTokenFile) add('css.token', path, 'Define visual tokens only in the design-system token files.', line);
        for (const match of decl.value.matchAll(/var\(\s*(--[\w-]+)/g)) if (!tokens.has(match[1])) add('css.token', path, 'Referenced visual token is not defined in the design system.', line);
        if (feature && !layout.test(prop)) add('css.feature', path, 'Feature CSS may arrange shared components only; move presentation to the library.', line);
        if (!isTokenFile && /#[0-9a-f]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|oklch|oklab|lab|lch)\s*\(|(?:\d*\.)?\d+(?:px|rem|em)\b/i.test(decl.value)) add('css.literal', path, 'Use semantic tokens instead of literal colors, typography, or dimensions.', line);
        if (!isTokenFile && /^(color|background(?:-color)?|fill|stroke|box-shadow)$/.test(prop)) {
          const cleaned = decl.value.replace(/var\(\s*--[\w-]+\s*\)/g, 'TOKEN');
          if (!/^(TOKEN|transparent|inherit|currentColor|initial|unset|none|\s)+$/.test(cleaned)) add('css.literal', path, 'Color and shadow values must come from semantic tokens.', line);
        }
      });
      css.walkAtRules((rule) => {
        if (rule.name === 'import') {
          const match = rule.params.match(/['"]([^'"]+)['"]/);
          if (!match || /^(https?:|\/\/)/.test(match[1])) add('css.import', path, 'External styles/fonts are not approved shared assets.', rule.source?.start?.line ?? 1);
          else checkImport(path, match[1], rule.source?.start?.line ?? 1);
        }
        if (rule.name === 'media') for (const match of rule.params.matchAll(/(?:min|max)-width:\s*([\d.]+(?:px|rem|em))/g)) {
          if (!policy.breakpoints.includes(match[1])) add('css.breakpoint', path, 'Use a documented shared responsive breakpoint.', rule.source?.start?.line ?? 1);
        }
      });
    }
  }

  const graph = {};
  for (const [name, { path, manifest }] of Object.entries(byName)) {
    const owner = ownerOf(path, policy);
    if (!owner) continue;
    graph[name] = [];
    for (const dependency of Object.keys(dependencies(manifest, false))) {
      const target = policy.node_packages[dependency];
      if (target) {
        graph[name].push(dependency);
        if (!permits(owner, target, policy)) add('manifest.dependencies', path, 'Declared package dependency violates the ownership graph.');
      }
    }
  }
  const visiting = new Set(), visited = new Set();
  function visit(name) {
    if (visiting.has(name)) { add('manifest.cycle', byName[name].path, 'Workspace dependencies contain a cycle.'); return; }
    if (visited.has(name)) return;
    visiting.add(name);
    (graph[name] ?? []).forEach(visit);
    visiting.delete(name); visited.add(name);
  }
  Object.keys(graph).forEach(visit);
  return findings;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  const { files, policy } = JSON.parse(readFileSync(0, 'utf8'));
  process.stdout.write(JSON.stringify(analyze(files, policy)));
}
