import { analyzeGraph } from "./analyzer/index.js";
import { buildGraph } from "./graph/index.js";
import { parseProject } from "./parser/index.js";

export async function analyzeProject(projectPath) {
  const parsedProject = await parseProject(projectPath);
  const graph = buildGraph(parsedProject);
  const analyzedGraph = analyzeGraph(graph);

  return {
    ...analyzedGraph,
    simple: {
      nodes: analyzedGraph.nodes.map((node) => node.id),
      edges: analyzedGraph.edges.map((edge) => [edge.source, edge.target]),
    },
  };
}
