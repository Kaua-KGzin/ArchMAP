export function parseJsTsImports(sourceCode) {
  const imports = new Set();

  const importExportRegex =
    /\b(?:import|export)\s+(?:type\s+)?(?:[^"'()]*?\s+from\s+)?["']([^"']+)["']/g;
  const requireRegex = /\brequire\(\s*["']([^"']+)["']\s*\)/g;
  const dynamicImportRegex = /\bimport\(\s*["']([^"']+)["']\s*\)/g;

  collectMatches(sourceCode, importExportRegex, imports);
  collectMatches(sourceCode, requireRegex, imports);
  collectMatches(sourceCode, dynamicImportRegex, imports);

  return [...imports];
}

function collectMatches(text, regex, targetSet) {
  let match = regex.exec(text);
  while (match) {
    const specifier = match[1]?.trim();
    if (specifier) {
      targetSet.add(specifier);
    }
    match = regex.exec(text);
  }
}
