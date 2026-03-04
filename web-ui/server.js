import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import express from "express";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const staticDirectory = path.join(__dirname, "static");

export async function startWebUi({ report, port = 3000, openBrowser = true }) {
  const app = express();

  app.get("/api/graph", (_request, response) => {
    response.json(report);
  });

  app.get("/api/health", (_request, response) => {
    response.json({ status: "ok" });
  });

  app.use(express.static(staticDirectory));
  app.get(/.*/, (_request, response) => {
    response.sendFile(path.join(staticDirectory, "index.html"));
  });

  return new Promise((resolve, reject) => {
    const server = app.listen(port, () => {
      const url = `http://localhost:${port}`;
      if (openBrowser) {
        tryOpenBrowser(url);
      }
      resolve({ server, url });
    });

    server.on("error", reject);
  });
}

function tryOpenBrowser(url) {
  try {
    const platform = process.platform;
    if (platform === "win32") {
      spawn("cmd", ["/c", "start", "", url], {
        detached: true,
        stdio: "ignore",
      }).unref();
      return;
    }
    if (platform === "darwin") {
      spawn("open", [url], { detached: true, stdio: "ignore" }).unref();
      return;
    }
    spawn("xdg-open", [url], { detached: true, stdio: "ignore" }).unref();
  } catch (error) {
    // Browser opening is best-effort only.
  }
}
