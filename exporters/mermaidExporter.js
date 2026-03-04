import fs from "node:fs/promises";
import path from "node:path";

export async function exportGraphAsMermaid(report, outputPath) {
  const absoluteOutputPath = path.resolve(outputPath);
  await fs.mkdir(path.dirname(absoluteOutputPath), { recursive: true });

  const lines = ["graph TD"];
  const nodeIds = new Set();

  for (const node of report.nodes) {
    const mermaidId = toMermaidNodeId(node.id, node.type);
    if (nodeIds.has(mermaidId)) {
      continue;
    }
    nodeIds.add(mermaidId);
    lines.push(`  ${mermaidId}[${toMermaidLabel(node.label)}]`);
  }

  for (const edge of report.edges) {
    const sourceId = toMermaidNodeId(edge.source, inferNodeType(edge.source));
    const targetId = toMermaidNodeId(edge.target, inferNodeType(edge.target));
    lines.push(`  ${sourceId} --> ${targetId}`);
  }

  lines.push("");
  await fs.writeFile(absoluteOutputPath, lines.join("\n"), "utf8");
  return absoluteOutputPath;
}

function toMermaidNodeId(nodeId, nodeType) {
  const prefix = nodeType === "package" ? "pkg_" : "file_";
  const stableId = nodeId.replace(/^pkg:/, "");
  const sanitized = stableId.replace(/[^a-zA-Z0-9_]/g, "_");
  return `${prefix}${sanitized}`;
}

function inferNodeType(nodeId) {
  return nodeId.startsWith("pkg:") ? "package" : "file";
}

function toMermaidLabel(label) {
  return JSON.stringify(String(label)).replace(/^"|"$/g, "");
}
