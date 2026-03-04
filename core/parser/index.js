import fs from "node:fs/promises";
import path from "node:path";

import glob from "fast-glob";

import {
  DEFAULT_IGNORE_PATTERNS,
  LANGUAGE_BY_EXTENSION,
  SUPPORTED_EXTENSIONS,
} from "./constants.js";
import { parseJsTsImports } from "./jsTsParser.js";
import { parsePythonImports } from "./pythonParser.js";
import { parseRustImports } from "./rustParser.js";
import { resolveDependenciesForFile, toFileId } from "./resolver.js";

export async function parseProject(projectPath) {
  const projectRoot = path.resolve(projectPath);
  const patterns = SUPPORTED_EXTENSIONS.map((extension) => `**/*${extension}`);

  const sourceFiles = await glob(patterns, {
    cwd: projectRoot,
    absolute: true,
    onlyFiles: true,
    ignore: DEFAULT_IGNORE_PATTERNS,
    dot: false,
    caseSensitiveMatch: false,
  });

  const normalizedFiles = sourceFiles.map((absolutePath) => path.resolve(absolutePath));
  const fileSet = new Set(normalizedFiles);
  const existsCache = new Map();

  const parsedFiles = [];

  for (const filePath of normalizedFiles) {
    const extension = path.extname(filePath).toLowerCase();
    const language = LANGUAGE_BY_EXTENSION[extension];

    if (!language) {
      continue;
    }

    let sourceCode = "";
    try {
      sourceCode = await fs.readFile(filePath, "utf8");
    } catch (error) {
      continue;
    }

    const imports = parseImportsByLanguage(language, sourceCode);
    const dependencies = resolveDependenciesForFile({
      language,
      imports,
      filePath,
      projectRoot,
      fileSet,
      existsCache,
    });

    const fileId = toFileId(projectRoot, filePath);

    parsedFiles.push({
      id: fileId,
      label: fileId,
      type: "file",
      language,
      absolutePath: filePath,
      dependencies,
    });
  }

  return {
    projectRoot,
    parsedFiles,
  };
}

function parseImportsByLanguage(language, sourceCode) {
  if (language === "javascript" || language === "typescript") {
    return parseJsTsImports(sourceCode);
  }
  if (language === "python") {
    return parsePythonImports(sourceCode);
  }
  if (language === "rust") {
    return parseRustImports(sourceCode);
  }
  return [];
}
