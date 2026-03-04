export const JS_TS_EXTENSIONS = [
  ".js",
  ".jsx",
  ".mjs",
  ".cjs",
  ".ts",
  ".tsx",
  ".mts",
  ".cts",
];

export const PYTHON_EXTENSIONS = [".py"];
export const RUST_EXTENSIONS = [".rs"];

export const SUPPORTED_EXTENSIONS = [
  ...JS_TS_EXTENSIONS,
  ...PYTHON_EXTENSIONS,
  ...RUST_EXTENSIONS,
];

export const LANGUAGE_BY_EXTENSION = {
  ".js": "javascript",
  ".jsx": "javascript",
  ".mjs": "javascript",
  ".cjs": "javascript",
  ".ts": "typescript",
  ".tsx": "typescript",
  ".mts": "typescript",
  ".cts": "typescript",
  ".py": "python",
  ".rs": "rust",
};

export const DEFAULT_IGNORE_PATTERNS = [
  "**/.git/**",
  "**/node_modules/**",
  "**/dist/**",
  "**/build/**",
  "**/target/**",
  "**/coverage/**",
  "**/__pycache__/**",
  "**/.venv/**",
  "**/venv/**",
];
