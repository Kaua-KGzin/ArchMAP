export function analyzeGraph(graph) {
  const fileNodes = graph.nodes.filter((node) => node.type === "file");
  const fileNodeIds = new Set(fileNodes.map((node) => node.id));

  const fileAdjacency = buildFileAdjacency(fileNodes, graph.edges, fileNodeIds);
  const cycles = findCircularDependencies(fileNodes, fileAdjacency);

  const cycleMap = buildCycleMembershipMap(cycles);
  const maxOutgoing = Math.max(...fileNodes.map((node) => node.outgoing), 0);

  const nodes = graph.nodes.map((node) => {
    if (node.type !== "file") {
      return {
        ...node,
        isCircular: cycleMap.has(node.id),
        complexityImports: 0,
        complexityScore: 0,
      };
    }

    return {
      ...node,
      isCircular: cycleMap.has(node.id),
      complexityImports: node.outgoing,
      complexityScore: toComplexityScore(node.outgoing, maxOutgoing),
    };
  });

  const edges = graph.edges.map((edge) => ({
    ...edge,
    isCircular: isCircularEdge(edge, cycleMap),
  }));

  const metrics = {
    filesAnalyzed: fileNodes.length,
    totalDependencies: graph.edges.length,
    externalDependencies: graph.nodes.filter((node) => node.type === "package").length,
    circularDependencyCount: cycles.length,
    complexity: summarizeComplexity(nodes),
    criticalFiles: summarizeCriticalFiles(nodes),
  };

  return {
    projectRoot: graph.projectRoot,
    nodes,
    edges,
    metrics,
    cycles,
  };
}

function buildFileAdjacency(fileNodes, edges, fileNodeIds) {
  const adjacency = new Map();
  for (const fileNode of fileNodes) {
    adjacency.set(fileNode.id, []);
  }

  for (const edge of edges) {
    if (!fileNodeIds.has(edge.source) || !fileNodeIds.has(edge.target)) {
      continue;
    }
    adjacency.get(edge.source).push(edge.target);
  }

  return adjacency;
}

function summarizeComplexity(nodes) {
  return nodes
    .filter((node) => node.type === "file")
    .map((node) => ({
      file: node.id,
      imports: node.outgoing,
      score: node.complexityScore,
    }))
    .sort((left, right) => right.score - left.score || left.file.localeCompare(right.file));
}

function summarizeCriticalFiles(nodes) {
  return nodes
    .filter((node) => node.type === "file")
    .map((node) => ({
      file: node.id,
      dependents: node.incoming,
    }))
    .sort(
      (left, right) => right.dependents - left.dependents || left.file.localeCompare(right.file)
    );
}

function buildCycleMembershipMap(cycles) {
  const membership = new Map();

  cycles.forEach((cycle, index) => {
    for (const nodeId of cycle) {
      membership.set(nodeId, index);
    }
  });

  return membership;
}

function isCircularEdge(edge, cycleMap) {
  if (!cycleMap.has(edge.source) || !cycleMap.has(edge.target)) {
    return false;
  }

  return cycleMap.get(edge.source) === cycleMap.get(edge.target);
}

function toComplexityScore(outgoingImports, maxOutgoingImports) {
  if (maxOutgoingImports <= 0) {
    return 0;
  }
  return Number((outgoingImports / maxOutgoingImports).toFixed(6));
}

function findCircularDependencies(fileNodes, adjacency) {
  let index = 0;
  const stack = [];
  const onStack = new Set();
  const indices = new Map();
  const lowlinks = new Map();
  const components = [];

  const strongConnect = (nodeId) => {
    indices.set(nodeId, index);
    lowlinks.set(nodeId, index);
    index += 1;

    stack.push(nodeId);
    onStack.add(nodeId);

    for (const neighbor of adjacency.get(nodeId) ?? []) {
      if (!indices.has(neighbor)) {
        strongConnect(neighbor);
        lowlinks.set(nodeId, Math.min(lowlinks.get(nodeId), lowlinks.get(neighbor)));
      } else if (onStack.has(neighbor)) {
        lowlinks.set(nodeId, Math.min(lowlinks.get(nodeId), indices.get(neighbor)));
      }
    }

    if (lowlinks.get(nodeId) === indices.get(nodeId)) {
      const component = [];
      let currentId = null;

      while (currentId !== nodeId && stack.length > 0) {
        currentId = stack.pop();
        onStack.delete(currentId);
        component.push(currentId);
      }

      if (component.length > 1) {
        components.push(component.sort());
      } else {
        const targetList = adjacency.get(component[0]) ?? [];
        if (targetList.includes(component[0])) {
          components.push(component);
        }
      }
    }
  };

  for (const fileNode of fileNodes) {
    if (!indices.has(fileNode.id)) {
      strongConnect(fileNode.id);
    }
  }

  return components.sort((left, right) => left[0].localeCompare(right[0]));
}
