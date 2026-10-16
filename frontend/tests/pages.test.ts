import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

/**
 * Guards against the defect that broke the Vercel build: a component rendered
 * in JSX with no binding in scope.
 *
 * `next build` catches this (`react/jsx-no-undef`) and `tsc --noEmit` catches
 * it too (TS2304) — but both only run if they run on the code actually being
 * shipped. This test is the same check, made cheap and impossible to skip.
 *
 * It parses the real TypeScript AST rather than pattern-matching the source.
 * That distinction matters: a regex that looks for `<Component` cannot tell a
 * JSX element from a generic type argument, so `useState<TabId>('dashboard')`
 * reads as a rendered component and produces a false failure. The AST knows
 * the difference, so this test only fires on genuine JSX.
 */

const ROOT = path.resolve(__dirname, '..');

/** Identifiers that are in scope in any TSX module without an import. */
const AMBIENT = new Set(['React']);

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    // Skip dotdirs (.next, .git) and dependencies.
    if (entry.name === 'node_modules' || entry.name.startsWith('.')) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (/\.tsx$/.test(entry.name)) out.push(full);
  }
  return out;
}

/** Every name an import clause binds into module scope. */
function bindingsFromImport(node: ts.ImportDeclaration): string[] {
  const clause = node.importClause;
  if (!clause) return []; // side-effect import: `import './x.css'`

  const names: string[] = [];
  if (clause.name) names.push(clause.name.text);

  const bindings = clause.namedBindings;
  if (bindings) {
    if (ts.isNamespaceImport(bindings)) {
      names.push(bindings.name.text);
    } else {
      for (const element of bindings.elements) names.push(element.name.text);
    }
  }
  return names;
}

/** Every name declared at any level of the file (fn, const, class, type…). */
function declaredNames(source: ts.SourceFile): string[] {
  const names: string[] = [];
  const visit = (node: ts.Node): void => {
    if (ts.isFunctionDeclaration(node) && node.name) names.push(node.name.text);
    else if (ts.isClassDeclaration(node) && node.name) names.push(node.name.text);
    else if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
      names.push(node.name.text);
    } else if (ts.isTypeAliasDeclaration(node) || ts.isInterfaceDeclaration(node)) {
      names.push(node.name.text);
    } else if (ts.isEnumDeclaration(node)) names.push(node.name.text);
    ts.forEachChild(node, visit);
  };
  visit(source);
  return names;
}

/** Capitalised identifiers actually rendered as JSX elements. */
function renderedTags(source: ts.SourceFile): { name: string; pos: number }[] {
  const tags: { name: string; pos: number }[] = [];
  const visit = (node: ts.Node): void => {
    const tag =
      ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)
        ? node.tagName
        : undefined;
    if (tag && ts.isIdentifier(tag) && /^[A-Z]/.test(tag.text)) {
      const { line } = source.getLineAndCharacterOfPosition(tag.getStart(source));
      tags.push({ name: tag.text, pos: line + 1 });
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return tags;
}

function parse(file: string): ts.SourceFile {
  return ts.createSourceFile(
    file,
    fs.readFileSync(file, 'utf8'),
    ts.ScriptTarget.Latest,
    /* setParentNodes */ true,
    ts.ScriptKind.TSX,
  );
}

const appFiles = walk(ROOT);

describe('app JSX integrity', () => {
  it('finds the app files it is supposed to guard', () => {
    // Without this, a broken glob would silently pass everything below.
    expect(appFiles.length).toBeGreaterThan(0);
  });

  for (const file of appFiles) {
    const rel = path.relative(ROOT, file);

    it(`${rel} imports every component it renders`, () => {
      const source = parse(file);

      const bound = new Set<string>(AMBIENT);
      for (const statement of source.statements) {
        if (ts.isImportDeclaration(statement)) {
          for (const name of bindingsFromImport(statement)) bound.add(name);
        }
      }
      for (const name of declaredNames(source)) bound.add(name);

      const missing = renderedTags(source).filter((tag) => !bound.has(tag.name));

      expect(
        missing,
        missing.length
          ? `${rel} renders ${missing
              .map((tag) => `${tag.name} (line ${tag.pos})`)
              .join(', ')} with no import or local declaration. ` +
            `This is the "react/jsx-no-undef" / TS2304 build failure.`
          : undefined,
      ).toEqual([]);
    });
  }
});
