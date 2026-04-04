import path from "node:path";

import { createPythonReportProvider, startWebUi } from "./server.js";

const args = parseArgs(process.argv.slice(2));
const projectPath = args.path ?? ".";
const host = args.host ?? "0.0.0.0";
const port = args.port ?? 3000;
const openBrowser = !args.noOpen;
const pythonCmd = args.python ?? "python";

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
  staticDir: path.join(process.cwd(), "src", "archmap", "web-ui", "static"),
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
