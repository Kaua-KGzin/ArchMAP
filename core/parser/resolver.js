import fs from "node:fs";
import path from "node:path";

import { JS_TS_EXTENSIONS } from "./constants.js";

const JS_TS_RESOLUTION_EXTENSIONS = [...new Set([...JS_TS_EXTENSIONS, ".json"])];

export function resolveDependenciesForFile({
  language,
  imports,
  filePath,
  projectRoot,
  fileSet,
  existsCache,
}) {
  if (!imports?.length) {
    return [];
  }

  let resolvedDependencies = [];

  if (language === "javascript" || language === "typescript") {
    resolvedDependencies = imports
      .map((specifier) =>
        resolveJsTsDependency(specifier, filePath, projectRoot, fileSet, existsCache)
      )
      .filter(Boolean);
  } else if (language === "python") {
    for (const importEntry of imports) {
      const pythonDeps = resolvePythonDependency(
        importEntry,
        filePath,
        projectRoot,
        fileSet,
        existsCache
      );
      resolvedDependencies.push(...pythonDeps);
    }
  } else if (language === "rust") {
    for (const importEntry of imports) {
      const rustDeps = resolveRustDependency(
        importEntry,
        filePath,
        projectRoot,
        fileSet,
        existsCache
      );
      resolvedDependencies.push(...rustDeps);
    }
  }

  return dedupeDependencies(resolvedDependencies);
}

export function toPosixPath(filePath) {
  return filePath.split(path.sep).join("/");
}

export function toFileId(projectRoot, absoluteFilePath) {
  return toPosixPath(path.relative(projectRoot, absoluteFilePath));
}

function dedupeDependencies(dependencies) {
  const seen = new Set();
  const deduped = [];

  for (const dependency of dependencies) {
    if (!dependency?.id || seen.has(dependency.id)) {
      continue;
    }
    seen.add(dependency.id);
    deduped.push(dependency);
  }

  return deduped;
}

function resolveJsTsDependency(specifier, filePath, projectRoot, fileSet, existsCache) {
  if (isLocalSpecifier(specifier)) {
    const resolutionBase = specifier.startsWith("/")
      ? projectRoot
      : path.dirname(filePath);
    const absoluteCandidate = path.resolve(resolutionBase, specifier);
    const resolvedPath = findMatchingFile(
      absoluteCandidate,
      JS_TS_RESOLUTION_EXTENSIONS,
      fileSet,
      existsCache
    );

    if (resolvedPath) {
      return makeFileDependency(projectRoot, resolvedPath);
    }

    return null;
  }

  const packageName = extractPackageName(specifier);
  return packageName ? makePackageDependency(packageName) : null;
}

function resolvePythonDependency(importEntry, filePath, projectRoot, fileSet, existsCache) {
  if (importEntry.type === "import") {
    const absoluteModulePath = findPythonAbsoluteModulePath(
      importEntry.module,
      projectRoot,
      fileSet,
      existsCache
    );

    if (absoluteModulePath) {
      return [makeFileDependency(projectRoot, absoluteModulePath)];
    }

    const packageName = extractPackageName(importEntry.module);
    return packageName ? [makePackageDependency(packageName)] : [];
  }

  if (importEntry.type === "from") {
    if (importEntry.module.startsWith(".")) {
      return resolveRelativePythonFromImport(
        importEntry.module,
        importEntry.names ?? [],
        filePath,
        projectRoot,
        fileSet,
        existsCache
      );
    }

    const absoluteModulePath = findPythonAbsoluteModulePath(
      importEntry.module,
      projectRoot,
      fileSet,
      existsCache
    );

    if (absoluteModulePath) {
      return [makeFileDependency(projectRoot, absoluteModulePath)];
    }

    const packageName = extractPackageName(importEntry.module);
    return packageName ? [makePackageDependency(packageName)] : [];
  }

  return [];
}

function resolveRustDependency(importEntry, filePath, projectRoot, fileSet, existsCache) {
  if (importEntry.type === "mod") {
    const moduleCandidate = path.join(path.dirname(filePath), importEntry.module);
    const resolvedModule = findRustModuleFile(moduleCandidate, fileSet, existsCache);
    return resolvedModule ? [makeFileDependency(projectRoot, resolvedModule)] : [];
  }

  if (importEntry.type === "extern") {
    return [makePackageDependency(importEntry.crate)];
  }

  if (importEntry.type !== "use") {
    return [];
  }

  const usePath = importEntry.path;
  const sourceRoot = inferRustSourceRoot(filePath, projectRoot);

  if (usePath.startsWith("crate::")) {
    const parts = usePath.replace(/^crate::/, "").split("::").filter(Boolean);
    const resolvedInternalPath = resolveRustPathByPrefix(
      sourceRoot,
      parts,
      fileSet,
      existsCache
    );
    return resolvedInternalPath
      ? [makeFileDependency(projectRoot, resolvedInternalPath)]
      : [];
  }

  if (usePath.startsWith("self::")) {
    const parts = usePath.replace(/^self::/, "").split("::").filter(Boolean);
    const resolvedInternalPath = resolveRustPathByPrefix(
      path.dirname(filePath),
      parts,
      fileSet,
      existsCache
    );
    return resolvedInternalPath
      ? [makeFileDependency(projectRoot, resolvedInternalPath)]
      : [];
  }

  if (usePath.startsWith("super::")) {
    const parts = usePath.split("::");
    let parentLevel = 0;
    while (parts[parentLevel] === "super") {
      parentLevel += 1;
    }

    let baseDir = path.dirname(filePath);
    for (let index = 0; index < parentLevel; index += 1) {
      baseDir = path.dirname(baseDir);
    }

    const moduleParts = parts.slice(parentLevel).filter(Boolean);
    const resolvedInternalPath = resolveRustPathByPrefix(
      baseDir,
      moduleParts,
      fileSet,
      existsCache
    );
    return resolvedInternalPath
      ? [makeFileDependency(projectRoot, resolvedInternalPath)]
      : [];
  }

  const plainParts = usePath.split("::").filter(Boolean);
  const maybeInternalPath = resolveRustPathByPrefix(
    sourceRoot,
    plainParts,
    fileSet,
    existsCache
  );

  if (maybeInternalPath) {
    return [makeFileDependency(projectRoot, maybeInternalPath)];
  }

  const packageName = plainParts[0];
  return packageName ? [makePackageDependency(packageName)] : [];
}

function resolveRelativePythonFromImport(
  modulePath,
  importedNames,
  filePath,
  projectRoot,
  fileSet,
  existsCache
) {
  const { dotCount, remainder } = splitLeadingDots(modulePath);

  let baseDir = path.dirname(filePath);
  for (let index = 1; index < dotCount; index += 1) {
    baseDir = path.dirname(baseDir);
  }

  const targets = [];

  if (remainder) {
    const resolvedPath = findPythonRelativeModulePath(
      baseDir,
      remainder,
      fileSet,
      existsCache
    );

    if (resolvedPath) {
      targets.push(makeFileDependency(projectRoot, resolvedPath));
    }
  } else {
    for (const importedName of importedNames) {
      if (importedName === "*") {
        continue;
      }

      const resolvedPath = findPythonRelativeModulePath(
        baseDir,
        importedName,
        fileSet,
        existsCache
      );

      if (resolvedPath) {
        targets.push(makeFileDependency(projectRoot, resolvedPath));
      }
    }
  }

  return dedupeDependencies(targets);
}

function splitLeadingDots(modulePath) {
  const match = modulePath.match(/^(\.+)(.*)$/);
  if (!match) {
    return { dotCount: 0, remainder: modulePath };
  }
  return { dotCount: match[1].length, remainder: match[2] };
}

function findPythonAbsoluteModulePath(moduleName, projectRoot, fileSet, existsCache) {
  if (!moduleName) {
    return null;
  }

  const baseCandidate = path.join(projectRoot, ...moduleName.split("."));
  return findPythonModuleFile(baseCandidate, fileSet, existsCache);
}

function findPythonRelativeModulePath(baseDir, moduleName, fileSet, existsCache) {
  if (!moduleName) {
    return null;
  }

  const baseCandidate = path.join(baseDir, ...moduleName.split("."));
  return findPythonModuleFile(baseCandidate, fileSet, existsCache);
}

function findPythonModuleFile(baseCandidate, fileSet, existsCache) {
  const directModule = `${baseCandidate}.py`;
  if (fileExists(directModule, fileSet, existsCache)) {
    return directModule;
  }

  const packageModule = path.join(baseCandidate, "__init__.py");
  if (fileExists(packageModule, fileSet, existsCache)) {
    return packageModule;
  }

  return null;
}

function inferRustSourceRoot(filePath, projectRoot) {
  const segments = path.resolve(filePath).split(path.sep);
  const sourceIndex = segments.lastIndexOf("src");

  if (sourceIndex >= 0) {
    return segments.slice(0, sourceIndex + 1).join(path.sep);
  }

  return projectRoot;
}

function resolveRustPathByPrefix(baseDir, moduleParts, fileSet, existsCache) {
  if (!moduleParts.length) {
    return null;
  }

  for (let length = moduleParts.length; length >= 1; length -= 1) {
    const partialPath = path.join(baseDir, ...moduleParts.slice(0, length));
    const resolvedPath = findRustModuleFile(partialPath, fileSet, existsCache);
    if (resolvedPath) {
      return resolvedPath;
    }
  }

  return null;
}

function findRustModuleFile(baseCandidate, fileSet, existsCache) {
  const directModule = `${baseCandidate}.rs`;
  if (fileExists(directModule, fileSet, existsCache)) {
    return directModule;
  }

  const nestedModule = path.join(baseCandidate, "mod.rs");
  if (fileExists(nestedModule, fileSet, existsCache)) {
    return nestedModule;
  }

  return null;
}

function isLocalSpecifier(specifier) {
  return specifier.startsWith(".") || specifier.startsWith("/");
}

function extractPackageName(specifier) {
  if (!specifier) {
    return null;
  }

  if (specifier.startsWith("@")) {
    const [scope, name] = specifier.split("/");
    return scope && name ? `${scope}/${name}` : specifier;
  }

  return specifier.split("/")[0];
}

function findMatchingFile(baseCandidate, extensions, fileSet, existsCache) {
  if (path.extname(baseCandidate)) {
    if (fileExists(baseCandidate, fileSet, existsCache)) {
      return baseCandidate;
    }
  }

  for (const extension of extensions) {
    const candidateWithExtension = `${baseCandidate}${extension}`;
    if (fileExists(candidateWithExtension, fileSet, existsCache)) {
      return candidateWithExtension;
    }
  }

  for (const extension of extensions) {
    const candidateIndex = path.join(baseCandidate, `index${extension}`);
    if (fileExists(candidateIndex, fileSet, existsCache)) {
      return candidateIndex;
    }
  }

  return null;
}

function fileExists(absolutePath, fileSet, existsCache) {
  const normalizedPath = path.resolve(absolutePath);

  if (fileSet.has(normalizedPath)) {
    return true;
  }

  if (existsCache.has(normalizedPath)) {
    return existsCache.get(normalizedPath);
  }

  const existsOnDisk = fs.existsSync(normalizedPath);
  existsCache.set(normalizedPath, existsOnDisk);
  return existsOnDisk;
}

function makeFileDependency(projectRoot, absolutePath) {
  const id = toFileId(projectRoot, path.resolve(absolutePath));
  return {
    id,
    label: id,
    type: "file",
  };
}

function makePackageDependency(packageName) {
  const id = `pkg:${packageName}`;
  return {
    id,
    label: packageName,
    type: "package",
  };
}
