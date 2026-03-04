export function buildGraph(parsedProject) {
  const nodeMap = new Map();
  const edgeMap = new Map();

  for (const file of parsedProject.parsedFiles) {
    nodeMap.set(file.id, {
      id: file.id,
      label: file.label,
      type: "file",
      language: file.language,
      folder: inferTopLevelFolder(file.id),
      outgoing: 0,
      incoming: 0,
      isCircular: false,
    });
  }

  for (const file of parsedProject.parsedFiles) {
    for (const dependency of file.dependencies) {
      if (!nodeMap.has(dependency.id)) {
        nodeMap.set(dependency.id, {
          id: dependency.id,
          label: dependency.label,
          type: dependency.type,
          language: dependency.type === "file" ? "unknown" : "package",
          folder: dependency.type === "file" ? inferTopLevelFolder(dependency.id) : "(external)",
          outgoing: 0,
          incoming: 0,
          isCircular: false,
        });
      }

      const edgeId = `${file.id}->${dependency.id}`;
      if (!edgeMap.has(edgeId)) {
        edgeMap.set(edgeId, {
          id: edgeId,
          source: file.id,
          target: dependency.id,
          isCircular: false,
        });
      }
    }
  }

  const nodes = [...nodeMap.values()].sort(compareNodes);
  const edges = [...edgeMap.values()].sort(compareEdges);

  for (const edge of edges) {
    const sourceNode = nodeMap.get(edge.source);
    const targetNode = nodeMap.get(edge.target);

    if (sourceNode) {
      sourceNode.outgoing += 1;
    }
    if (targetNode) {
      targetNode.incoming += 1;
    }
  }

  return {
    projectRoot: parsedProject.projectRoot,
    nodes,
    edges,
  };
}

function inferTopLevelFolder(fileId) {
  const segments = fileId.split("/");
  return segments.length > 1 ? segments[0] : ".";
}

function compareNodes(leftNode, rightNode) {
  if (leftNode.type !== rightNode.type) {
    return leftNode.type === "file" ? -1 : 1;
  }
  return leftNode.id.localeCompare(rightNode.id);
}

function compareEdges(leftEdge, rightEdge) {
  return leftEdge.id.localeCompare(rightEdge.id);
}
