export function parsePythonImports(sourceCode) {
  const dependencies = [];

  const importRegex = /^\s*import\s+([^\n#]+)$/gm;
  const fromRegex = /^\s*from\s+([.a-zA-Z0-9_]+)\s+import\s+([^\n#]+)$/gm;

  let importMatch = importRegex.exec(sourceCode);
  while (importMatch) {
    const modules = sanitizeImportPart(importMatch[1])
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean)
      .map((entry) => entry.split(/\s+as\s+/)[0].trim())
      .filter(Boolean);

    for (const moduleName of modules) {
      dependencies.push({ type: "import", module: moduleName });
    }

    importMatch = importRegex.exec(sourceCode);
  }

  let fromMatch = fromRegex.exec(sourceCode);
  while (fromMatch) {
    const moduleName = fromMatch[1].trim();
    const names = sanitizeImportPart(fromMatch[2])
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean)
      .map((entry) => entry.split(/\s+as\s+/)[0].trim())
      .filter(Boolean);

    dependencies.push({ type: "from", module: moduleName, names });
    fromMatch = fromRegex.exec(sourceCode);
  }

  return dependencies;
}

function sanitizeImportPart(value) {
  return String(value).split("#")[0].trim();
}
