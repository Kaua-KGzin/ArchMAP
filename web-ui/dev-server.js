import { createPythonReportProvider, startWebUi } from "./server.js";

const args = parseArgs(process.argv.slice(2));
const projectPath = args.path ?? ".";
// Loopback by default, like `archmap serve`: the UI can switch the analyzed
// directory, so binding every interface must be an explicit --host choice.
const host = args.host ?? "127.0.0.1";
const port = args.port ?? 3000;
const openBrowser = !args.noOpen;
const pythonCmd = args.python ?? (process.platform === "win32" ? "python" : "python3");

const reportProvider = createPythonReportProvider({
  projectPath,
  pythonCmd,
});

const { url } = await startWebUi({
  reportProvider,
  projectPath,
  host,
  port,
  openBrowser,
  // staticDir: server.js already points at src/archmap/web-ui/static (the old
  // override pointed at web-ui/static, which doesn't exist).
});

console.log(`[info] ArchMAP web server running on ${url}`);
console.log(`[info] Project path: ${projectPath}`);

function parseArgs(rawArgs) {
  const parsed = {};
  for (let index = 0; index < rawArgs.length; index += 1) {
    const token = rawArgs[index];
    if (token === "--path") {
      parsed.path = rawArgs[index + 1];
      index += 1;
      continue;
    }
    if (token === "--host") {
      parsed.host = rawArgs[index + 1];
      index += 1;
      continue;
    }
    if (token === "--port") {
      parsed.port = Number.parseInt(rawArgs[index + 1], 10);
      index += 1;
      continue;
    }
    if (token === "--python") {
      parsed.python = rawArgs[index + 1];
      index += 1;
      continue;
    }
    if (token === "--no-open") {
      parsed.noOpen = true;
      continue;
    }
    if (!token.startsWith("-") && !parsed.path) {
      parsed.path = token;
    }
  }
  return parsed;
}
