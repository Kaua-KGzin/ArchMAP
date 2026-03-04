import fs from "node:fs/promises";
import path from "node:path";

export async function exportGraphAsJson(report, outputPath) {
  const absoluteOutputPath = path.resolve(outputPath);
  await fs.mkdir(path.dirname(absoluteOutputPath), { recursive: true });

  const payload = {
    projectRoot: report.projectRoot,
    generatedAt: new Date().toISOString(),
    nodes: report.simple.nodes,
    edges: report.simple.edges,
    metrics: report.metrics,
    cycles: report.cycles,
    detailed: {
      nodes: report.nodes,
      edges: report.edges,
    },
  };

  await fs.writeFile(absoluteOutputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return absoluteOutputPath;
}
