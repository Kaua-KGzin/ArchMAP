export function parseRustImports(sourceCode) {
  const dependencies = [];

  const useRegex = /^\s*use\s+([^;]+);/gm;
  const modRegex = /^\s*mod\s+([a-zA-Z0-9_]+)\s*;/gm;
  const externRegex = /^\s*extern\s+crate\s+([a-zA-Z0-9_]+)\s*;/gm;

  let useMatch = useRegex.exec(sourceCode);
  while (useMatch) {
    const normalizedUsePath = normalizeRustUsePath(useMatch[1]);
    if (normalizedUsePath) {
      dependencies.push({ type: "use", path: normalizedUsePath });
    }
    useMatch = useRegex.exec(sourceCode);
  }

  let modMatch = modRegex.exec(sourceCode);
  while (modMatch) {
    dependencies.push({ type: "mod", module: modMatch[1].trim() });
    modMatch = modRegex.exec(sourceCode);
  }

  let externMatch = externRegex.exec(sourceCode);
  while (externMatch) {
    dependencies.push({ type: "extern", crate: externMatch[1].trim() });
    externMatch = externRegex.exec(sourceCode);
  }

  return dependencies;
}

function normalizeRustUsePath(rawPath) {
  const compact = rawPath.replace(/\s+/g, " ").trim().replace(/^pub\s+/, "");
  const withoutAlias = compact.split(/\s+as\s+/)[0].trim();
  const withoutGroupedImports = withoutAlias.replace(/\{.*\}/, "").trim();
  const withoutWildcard = withoutGroupedImports.replace(/::\*$/, "").trim();
  const normalized = withoutWildcard.replace(/::$/, "").trim();
  return normalized;
}
