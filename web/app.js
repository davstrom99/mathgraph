let graph = null;
let selectedNodeId = null;
let selectedEdgeIndex = null;
let hoveredNodeId = null;
let hoveredEdgeIndex = null;
let transform = { x: 0, y: 0, scale: 1 };
let isPanning = false;
let panStart = null;
let graphLayout = null;
let graphViewport = null;
let selectionFramePending = false;
let transformFramePending = false;
let nodeElements = new Map();
let edgeElements = new Map();
let edgeLabelElements = new Map();
let clusterElements = new Map();

const detail = document.getElementById("detail");
const graphView = document.getElementById("graph-view");

const KIND_ORDER = [
  "variable", "assumption", "objective", "estimator", "approximation",
  "simulator", "experiment", "validation", "figure", "dataset", "test"
];

const KIND_COLORS = {
  variable: "#0ea5e9",
  assumption: "#f97316",
  objective: "#ec4899",
  estimator: "#ef4444",
  approximation: "#14b8a6",
  simulator: "#22c55e",
  experiment: "#64748b",
  validation: "#2563eb",
  figure: "#8b5cf6",
  dataset: "#eab308",
  test: "#475569",
  default: "#94a3b8",
};

fetch("graph.json")
  .then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(async (data) => {
    graph = data;
    selectedNodeId = graph.nodes[0]?.id || null;
    document.getElementById("project-title").textContent = graph.project.title || "Mathgraph";
    if (typeof ELK !== "function") throw new Error("Local elkjs bundle is unavailable.");
    attachGraphGestures();
    await renderGraph();
    renderNodeDetail();
    bindDetailButtons();
  })
  .catch((error) => {
    detail.innerHTML = `<p class="empty">Could not load graph.json: ${escapeHtml(error.message)}</p>`;
  });

async function renderGraph() {
  const layout = await layoutGraph();
  graphLayout = layout;
  graphView.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
  const related = relatedIds();
  const legendKinds = Array.from(new Set(graph.nodes.map((node) => node.kind))).sort();
  graphView.innerHTML = `
    <defs>
      <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
        <path d="M0,0 L10,4 L0,8 z" fill="#a5b0bd"></path>
      </marker>
      <marker id="arrow-active" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
        <path d="M0,0 L10,4 L0,8 z" fill="#1d4ed8"></path>
      </marker>
    </defs>
    <g id="graph-viewport">
      ${layout.clusters.map((cluster) => renderCluster(cluster, related)).join("")}
      ${graph.edges.map((edge, index) => renderGraphEdge(edge, index, layout.positions, related)).join("")}
      ${graph.nodes.map((node) => renderGraphNode(node, layout.positions.get(node.id), related)).join("")}
      ${legendKinds.map((kind, index) => renderLegendItem(kind, layout.width - 160, layout.height - 26 - index * 20)).join("")}
    </g>
  `;
  graphViewport = document.getElementById("graph-viewport");
  nodeElements = new Map(Array.from(graphView.querySelectorAll(".graph-node")).map((element) => [element.dataset.nodeId, element]));
  edgeElements = new Map(Array.from(graphView.querySelectorAll(".graph-edge")).map((element) => [Number(element.dataset.edgeIndex), element]));
  edgeLabelElements = new Map(Array.from(graphView.querySelectorAll(".edge-label")).map((element) => [Number(element.dataset.edgeIndex), element]));
  clusterElements = new Map(Array.from(graphView.querySelectorAll(".graph-cluster")).map((element) => [element.dataset.clusterId, element]));
  applyGraphTransform();
  updateGraphSelection();
}

async function layoutGraph() {
  const elk = new ELK();
  const groups = buildSccGroups();
  const groupLayouts = await Promise.all(groups.map((group) => layoutGroup(elk, group)));
  const groupById = new Map(groupLayouts.map((group) => [group.id, group]));
  const groupIdByNode = new Map();
  for (const group of groups) {
    group.nodes.forEach((node) => groupIdByNode.set(node.id, group.id));
  }
  const edgeByRoute = new Map();
  graph.edges.forEach((edge, index) => {
    const fromGroup = groupIdByNode.get(edge.from);
    const toGroup = groupIdByNode.get(edge.to);
    if (!fromGroup || !toGroup || fromGroup === toGroup) return;
    const key = `${fromGroup}->${toGroup}`;
    if (!edgeByRoute.has(key)) edgeByRoute.set(key, []);
    edgeByRoute.get(key).push(index);
  });

  const root = await elk.layout({
    id: "mathgraph-root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.spacing.nodeNode": "70",
      "elk.layered.spacing.nodeNodeBetweenLayers": "120",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.padding": "[top=30,left=30,bottom=30,right=30]",
    },
    children: groupLayouts.map((group) => ({ id: group.id, width: group.width, height: group.height })),
    edges: Array.from(edgeByRoute.entries()).map(([route, edgeIndexes]) => {
      const [source, target] = route.split("->");
      return {
        id: `route:${route}`,
        sources: [source],
        targets: [target],
        labels: [{ text: String(edgeIndexes.length) }],
      };
    }),
  });

  const marginX = 120;
  const marginY = 90;
  const rootChildren = new Map((root.children || []).map((child) => [child.id, child]));
  const positions = new Map();
  const clusters = [];
  for (const group of groupLayouts) {
    const rootNode = rootChildren.get(group.id);
    const baseX = marginX + (rootNode?.x || 0);
    const baseY = marginY + (rootNode?.y || 0);
    if (group.members.length > 1) {
      clusters.push({
        id: group.id,
        x: baseX,
        y: baseY,
        width: group.width,
        height: group.height,
        label: `SCC (${group.members.length} nodes)`,
        members: group.members,
      });
    }
    for (const member of group.members) {
      const local = group.positions.get(member.id);
      if (!local) continue;
      positions.set(member.id, {
        x: baseX + local.x,
        y: baseY + local.y,
        width: local.width,
        height: local.height,
      });
    }
  }

  return {
    positions,
    clusters,
    width: marginX * 2 + (root.width || 900),
    height: marginY * 2 + (root.height || 700),
  };
}

function buildSccGroups() {
  const groups = [];
  const assigned = new Set();
  const graphClusters = Array.isArray(graph.clusters) ? graph.clusters : [];
  graphClusters.forEach((cluster) => {
    const members = cluster.members.map((nodeId) => findNode(nodeId)).filter(Boolean);
    members.forEach((node) => assigned.add(node.id));
    groups.push({ id: cluster.id, nodes: members, cluster });
  });
  graph.nodes
    .filter((node) => !assigned.has(node.id))
    .sort((a, b) => displayName(a).localeCompare(displayName(b)))
    .forEach((node) => {
      groups.push({ id: `node:${node.id}`, nodes: [node], cluster: null });
    });
  return groups;
}

async function layoutGroup(elk, group) {
  const internalEdges = graph.edges.filter((edge) =>
    group.nodes.some((node) => node.id === edge.from) &&
    group.nodes.some((node) => node.id === edge.to)
  );
  const positions = new Map();
  if (group.nodes.length === 1) {
    const only = group.nodes[0];
    const box = nodeBox(only);
    positions.set(only.id, { x: 0, y: 0, width: box.width, height: box.height });
    return {
      id: group.id,
      width: box.width,
      height: box.height,
      positions,
      members: group.nodes,
    };
  }

  const local = await elk.layout({
    id: group.id,
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.spacing.nodeNode": "26",
      "elk.layered.spacing.nodeNodeBetweenLayers": "38",
      "elk.edgeRouting": "POLYLINE",
      "elk.padding": "[top=12,left=12,bottom=12,right=12]",
    },
    children: group.nodes.map((node) => {
      const box = nodeBox(node);
      return { id: node.id, width: box.width, height: box.height };
    }),
    edges: internalEdges.map((edge, index) => ({
      id: `${group.id}:edge:${index}`,
      sources: [edge.from],
      targets: [edge.to],
    })),
  });

  const paddingX = 26;
  const paddingBottom = 24;
  const headerHeight = 32;
  const paddingTop = 22;
  (local.children || []).forEach((child) => {
    positions.set(child.id, {
      x: paddingX + (child.x || 0),
      y: headerHeight + paddingTop + (child.y || 0),
      width: child.width || nodeBox(findNode(child.id)).width,
      height: child.height || nodeBox(findNode(child.id)).height,
    });
  });

  return {
    id: group.id,
    width: paddingX * 2 + (local.width || 0),
    height: headerHeight + paddingTop + paddingBottom + (local.height || 0),
    positions,
    members: group.nodes,
  };
}

function scheduleGraphTransform() {
  if (transformFramePending) return;
  transformFramePending = true;
  window.requestAnimationFrame(() => {
    transformFramePending = false;
    applyGraphTransform();
  });
}

function applyGraphTransform() {
  if (!graphLayout || !graphViewport) return;
  graphViewport.setAttribute(
    "transform",
    `matrix(${transform.scale} 0 0 ${transform.scale} ${transform.x} ${transform.y})`
  );
}

function screenScale() {
  if (!graphLayout) return { x: 1, y: 1 };
  const rect = graphView.getBoundingClientRect();
  return {
    x: rect.width / Math.max(graphLayout.width, 1),
    y: rect.height / Math.max(graphLayout.height, 1),
  };
}

function normalizeWheelDelta(event) {
  if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) return event.deltaY * 16;
  if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) return event.deltaY * graphView.getBoundingClientRect().height;
  return event.deltaY;
}

function scheduleSelectionUpdate() {
  if (selectionFramePending) return;
  selectionFramePending = true;
  window.requestAnimationFrame(() => {
    selectionFramePending = false;
    updateGraphSelection();
  });
}

function updateGraphSelection() {
  const related = relatedIds();
  const activeClusters = new Set();
  related.nodes.forEach((nodeId) => {
    const cluster = findNode(nodeId)?.cluster;
    if (cluster?.id) activeClusters.add(cluster.id);
  });
  nodeElements.forEach((element, nodeId) => {
    element.classList.toggle("active", selectedNodeId === nodeId);
    element.classList.toggle("hovered", hoveredNodeId === nodeId);
    element.classList.toggle("neighbor", related.active && related.nodes.has(nodeId) && selectedNodeId !== nodeId);
    element.classList.toggle("dimmed", related.active && !related.nodes.has(nodeId));
  });
  edgeElements.forEach((element, edgeIndex) => {
    const active = selectedEdgeIndex === edgeIndex || related.edges.has(edgeIndex);
    const hovered = hoveredEdgeIndex === edgeIndex;
    element.classList.toggle("active", active);
    element.classList.toggle("hovered", hovered);
    element.classList.toggle("dimmed", related.active && !related.edges.has(edgeIndex));
    element.setAttribute("marker-end", `url(#${active || hovered ? "arrow-active" : "arrow"})`);
  });
  edgeLabelElements.forEach((element, edgeIndex) => {
    element.classList.toggle("visible", shouldShowEdgeLabel(edgeIndex));
  });
  clusterElements.forEach((element, clusterId) => {
    element.classList.toggle("active", activeClusters.has(clusterId) && selectedNodeId !== null);
    element.classList.toggle("neighbor", activeClusters.has(clusterId) && selectedNodeId === null && selectedEdgeIndex !== null);
    element.classList.toggle("dimmed", related.active && !activeClusters.has(clusterId));
  });
}

function attachGraphGestures() {
  graphView.addEventListener("click", (event) => {
    const nodeTarget = event.target.closest("[data-node-id]");
    if (nodeTarget) {
      event.stopPropagation();
      selectNode(nodeTarget.dataset.nodeId);
      return;
    }
    const edgeTarget = event.target.closest("[data-edge-index]");
    if (edgeTarget) {
      event.stopPropagation();
      selectEdge(Number(edgeTarget.dataset.edgeIndex));
    }
  });

  graphView.addEventListener("pointermove", (event) => {
    const nodeTarget = event.target.closest("[data-node-id]");
    const edgeTarget = nodeTarget ? null : event.target.closest("[data-edge-index]");
    const nextHoveredNodeId = nodeTarget?.dataset.nodeId || null;
    const nextHoveredEdgeIndex = edgeTarget ? Number(edgeTarget.dataset.edgeIndex) : null;
    if (nextHoveredNodeId === hoveredNodeId && nextHoveredEdgeIndex === hoveredEdgeIndex) return;
    hoveredNodeId = nextHoveredNodeId;
    hoveredEdgeIndex = nextHoveredEdgeIndex;
    scheduleSelectionUpdate();
  });

  graphView.addEventListener("pointerleave", () => {
    if (hoveredNodeId === null && hoveredEdgeIndex === null) return;
    hoveredNodeId = null;
    hoveredEdgeIndex = null;
    scheduleSelectionUpdate();
  });

  graphView.addEventListener("wheel", (event) => {
    event.preventDefault();
    const delta = normalizeWheelDelta(event);
    const factor = Math.exp(-delta * 0.002);
    zoomBy(factor, event.clientX, event.clientY);
  }, { passive: false });

  graphView.addEventListener("pointerdown", (event) => {
    if (event.target.closest("[data-node-id], [data-edge-index]")) return;
    isPanning = true;
    graphView.classList.add("dragging");
    panStart = { x: event.clientX, y: event.clientY, tx: transform.x, ty: transform.y };
    graphView.setPointerCapture(event.pointerId);
  });

  graphView.addEventListener("pointermove", (event) => {
    if (!isPanning || !panStart) return;
    const scale = screenScale();
    transform.x = panStart.tx + (event.clientX - panStart.x) / scale.x;
    transform.y = panStart.ty + (event.clientY - panStart.y) / scale.y;
    scheduleGraphTransform();
  });

  graphView.addEventListener("pointerup", (event) => {
    isPanning = false;
    panStart = null;
    graphView.classList.remove("dragging");
    try { graphView.releasePointerCapture(event.pointerId); } catch (error) {}
  });
}

function zoomBy(factor, clientX = null, clientY = null) {
  const oldScale = transform.scale;
  const newScale = oldScale * factor;
  if (!Number.isFinite(newScale) || newScale <= 0) return;
  if (newScale === oldScale) return;

  const rect = graphView.getBoundingClientRect();
  const scale = screenScale();
  const screen = clientX === null || clientY === null
    ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
    : { x: clientX, y: clientY };
  const localX = screen.x - rect.left;
  const localY = screen.y - rect.top;
  const anchor = screenToGraphPoint(screen.x, screen.y);

  transform.scale = newScale;
  transform.x = localX / scale.x - anchor.x * newScale;
  transform.y = localY / scale.y - anchor.y * newScale;
  scheduleGraphTransform();
}

function screenToGraphPoint(clientX, clientY) {
  const rect = graphView.getBoundingClientRect();
  const scale = screenScale();
  return {
    x: (((clientX - rect.left) / scale.x) - transform.x) / transform.scale,
    y: (((clientY - rect.top) / scale.y) - transform.y) / transform.scale,
  };
}

function relatedIds() {
  const nodes = new Set();
  const edges = new Set();
  if (selectedNodeId) {
    nodes.add(selectedNodeId);
    graph.edges.forEach((edge, index) => {
      if (edge.from === selectedNodeId || edge.to === selectedNodeId) {
        nodes.add(edge.from);
        nodes.add(edge.to);
        edges.add(index);
      }
    });
  }
  if (selectedEdgeIndex !== null) {
    const edge = graph.edges[selectedEdgeIndex];
    if (edge) {
      nodes.add(edge.from);
      nodes.add(edge.to);
      edges.add(selectedEdgeIndex);
    }
  }
  return { active: selectedNodeId !== null || selectedEdgeIndex !== null, nodes, edges };
}

function renderCluster(cluster, related) {
  const active = related.nodes.size > 0 && cluster.members.some((member) => related.nodes.has(member.id));
  const dimmed = related.active && !active;
  return `<g class="graph-cluster ${active ? "active" : ""} ${dimmed ? "dimmed" : ""}" data-cluster-id="${escapeAttr(cluster.id)}">
    <rect class="graph-cluster-card" x="${cluster.x}" y="${cluster.y}" width="${cluster.width}" height="${cluster.height}" rx="20"></rect>
    <text class="cluster-label" x="${cluster.x + 18}" y="${cluster.y + 22}">${escapeHtml(cluster.label)}</text>
  </g>`;
}

function renderGraphEdge(edge, index, positions, related) {
  const from = positions.get(edge.from);
  const to = positions.get(edge.to);
  if (!from || !to) return "";
  const start = edgeAnchor(from, to);
  const end = edgeAnchor(to, from);
  const deltaY = Math.abs(end.y - start.y);
  const controlOffset = Math.max(38, Math.min(120, deltaY * 0.55));
  const path = `M${start.x},${start.y} C${start.x},${start.y + controlOffset} ${end.x},${end.y - controlOffset} ${end.x},${end.y}`;
  const labelX = (start.x + end.x) / 2;
  const labelY = (start.y + end.y) / 2 - 9;
  const active = selectedEdgeIndex === index || related.edges.has(index) ? "active" : "";
  const dimmed = related.active && !related.edges.has(index) ? "dimmed" : "";
  const hovered = hoveredEdgeIndex === index ? "hovered" : "";
  const marker = active || hovered ? "arrow-active" : "arrow";
  return `<g data-edge-index="${index}">
    <path class="edge-hit" d="${path}" data-edge-index="${index}"></path>
    <path class="graph-edge ${active} ${hovered} ${dimmed}" d="${path}" marker-end="url(#${marker})" data-edge-index="${index}"></path>
    <text class="edge-label ${shouldShowEdgeLabel(index) ? "visible" : ""}" data-edge-index="${index}" x="${labelX}" y="${labelY}">${escapeHtml(edge.kind)}</text>
  </g>`;
}

function renderGraphNode(node, position, related) {
  if (!position) return "";
  const active = selectedNodeId === node.id ? "active" : "";
  const hovered = hoveredNodeId === node.id ? "hovered" : "";
  const neighbor = related.active && related.nodes.has(node.id) && selectedNodeId !== node.id ? "neighbor" : "";
  const dimmed = related.active && !related.nodes.has(node.id) ? "dimmed" : "";
  const box = nodeBox(node);
  const accent = kindColor(node.kind);
  return `<g class="graph-node ${active} ${hovered} ${neighbor} ${dimmed}" transform="translate(${position.x},${position.y})" data-node-id="${escapeAttr(node.id)}">
    <rect class="node-card" width="${box.width}" height="${box.height}" rx="16"></rect>
    <rect class="node-accent" width="8" height="${box.height}" rx="16" fill="${accent}"></rect>
    <circle cx="24" cy="24" r="7" fill="${accent}"></circle>
    ${node.titleImage
      ? `<image class="node-title-image" href="${escapeAttr(node.titleImage)}" x="40" y="13" width="${box.titleWidth}" height="${box.titleHeight}" preserveAspectRatio="xMinYMin meet"></image>`
      : `<text class="node-title-fallback" x="40" y="32">${escapeHtml(shorten(displayName(node), 34))}</text>`}
    <text class="node-kind" x="40" y="${box.height - 16}">${escapeHtml(node.kind)}</text>
  </g>`;
}

function renderLegendItem(kind, x, y) {
  return `<g transform="translate(${x},${y})">
    <circle r="5" fill="${kindColor(kind)}"></circle>
    <text class="edge-label" x="12" y="4">${escapeHtml(kind)}</text>
  </g>`;
}

function kindColor(kind) {
  return KIND_COLORS[kind] || KIND_COLORS.default;
}

function nodeBox(node) {
  return {
    width: Number(node.layout?.boxWidth || 190),
    height: Number(node.layout?.boxHeight || 82),
    titleWidth: Number(node.layout?.titleWidth || Math.max(120, displayName(node).length * 7.5)),
    titleHeight: Number(node.layout?.titleHeight || 24),
  };
}

function edgeAnchor(fromRect, toRect) {
  const fromCenter = centerOfRect(fromRect);
  const toCenter = centerOfRect(toRect);
  const dx = toCenter.x - fromCenter.x;
  const dy = toCenter.y - fromCenter.y;
  const halfWidth = fromRect.width / 2;
  const halfHeight = fromRect.height / 2;
  const scale = 1 / Math.max(Math.abs(dx) / halfWidth || 0, Math.abs(dy) / halfHeight || 0, 1);
  return {
    x: fromCenter.x + dx * scale,
    y: fromCenter.y + dy * scale,
  };
}

function centerOfRect(rect) {
  return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
}

function shouldShowEdgeLabel(edgeIndex) {
  if (selectedEdgeIndex === edgeIndex) return true;
  if (hoveredEdgeIndex === edgeIndex) return true;
  if (selectedNodeId) {
    const edge = graph.edges[edgeIndex];
    return edge && (edge.from === selectedNodeId || edge.to === selectedNodeId);
  }
  return false;
}

function findNode(nodeId) {
  return graph.nodes.find((candidate) => candidate.id === nodeId) || null;
}

function renderNodeDetail() {
  const node = findNode(selectedNodeId);
  if (!node) {
    detail.innerHTML = '<p class="empty">No node selected.</p>';
    return;
  }

  detail.innerHTML = `<article class="detail-inner">
    <h2>${renderNodeTitle(node)}</h2>
    <span class="badge">${escapeHtml(node.kind)}</span>
    <p class="empty">${escapeHtml(node.id)}</p>
    <p class="statement">${escapeHtml(node.statement)}</p>
    <div class="sections">
      ${section("TeX", renderTex(node.tex))}
      ${section("Variable Uses", renderStrings(node.uses))}
      ${section("Code", renderRefs(node.code))}
      ${section("Tests", renderRefs(node.tests))}
      ${section("Outputs", renderOutputs(node.outputs))}
      ${section("Incoming", renderEdges(node.incoming, "incoming"))}
      ${section("Outgoing", renderEdges(node.outgoing, "outgoing"))}
    </div>
  </article>`;
  bindDetailButtons();
}

function renderEdgeDetail() {
  const edge = graph.edges[selectedEdgeIndex];
  if (!edge) {
    detail.innerHTML = '<p class="empty">No edge selected.</p>';
    return;
  }
  detail.innerHTML = `<article class="detail-inner">
    <h2>${escapeHtml(edge.from)} -&gt; ${escapeHtml(edge.to)}</h2>
    <span class="badge">${escapeHtml(edge.kind)}</span>
    <p class="statement">${escapeHtml(edge.description)}</p>
    <div class="sections">
      ${section("Derivation", renderTex(edge.tex))}
      ${section("Input Node", renderNodeJump(edge.from))}
      ${section("Result Node", renderNodeJump(edge.to))}
    </div>
  </article>`;
  bindDetailButtons();
}

function renderNodeJump(nodeId) {
  const node = findNode(nodeId);
  if (!node) return `<p class="empty">${escapeHtml(nodeId)}</p>`;
  return `<button class="node-button" type="button" data-jump-node="${escapeAttr(node.id)}">
    <span class="node-id">${renderNodeTitle(node)}</span>
    <span class="node-title">${escapeHtml(node.id)}</span>
  </button>`;
}

function selectNode(nodeId) {
  selectedNodeId = nodeId;
  selectedEdgeIndex = null;
  scheduleSelectionUpdate();
  renderNodeDetail();
}

function selectEdge(edgeIndex) {
  selectedEdgeIndex = edgeIndex;
  selectedNodeId = null;
  scheduleSelectionUpdate();
  renderEdgeDetail();
}

function bindDetailButtons() {
  detail.querySelectorAll("[data-jump-node]").forEach((button) => {
    button.addEventListener("click", () => selectNode(button.dataset.jumpNode));
  });
  detail.querySelectorAll("[data-jump-edge]").forEach((button) => {
    button.addEventListener("click", () => selectEdge(Number(button.dataset.jumpEdge)));
  });
}

function section(title, body) {
  return `<section class="section"><h3>${escapeHtml(title)}</h3>${body}</section>`;
}

function renderTex(tex) {
  if (!tex) return '<p class="empty">none</p>';
  if (!tex.exists) {
    return `<ul class="ref-list"><li>${escapeHtml(tex.file)}#${escapeHtml(tex.label)} <span class="empty">(not generated yet)</span></li></ul>`;
  }
  return `<ul class="ref-list"><li><a href="${escapeAttr(tex.href)}">Rendered derivation</a><div class="link-label">${escapeHtml(tex.file)}#${escapeHtml(tex.label)}</div></li></ul>`;
}

function renderRefs(refs) {
  if (!refs || refs.length === 0) return '<p class="empty">none</p>';
  return `<ul class="ref-list">${refs.map((ref) => {
    if (!ref.exists) {
      return `<li>${escapeHtml(ref.label)} <span class="empty">(not generated yet)</span></li>`;
    }
    return `<li>
      <div class="link-label">${escapeHtml(ref.label)}${formatLines(ref)}</div>
      <a href="${escapeAttr(ref.href)}">Highlighted source</a>
      <a href="${escapeAttr(ref.vscodeHref)}">Open in VS Code</a>
    </li>`;
  }).join("")}</ul>`;
}

function renderOutputs(outputs) {
  if (!outputs || outputs.length === 0) return '<p class="empty">none</p>';
  return `<ul class="ref-list">${outputs.map((output) => {
    return `<li>${renderMaybeLink(output.href, output.path, output.exists)}</li>`;
  }).join("")}</ul>`;
}

function renderStrings(items) {
  if (!items || items.length === 0) return '<p class="empty">none</p>';
  return `<ul class="ref-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderEdges(edges, direction) {
  if (!edges || edges.length === 0) return '<p class="empty">none</p>';
  return `<ul class="edge-list">${edges.map((edge) => {
    const edgeIndex = graph.edges.findIndex((candidate) =>
      candidate.from === edge.from &&
      candidate.to === edge.to &&
      candidate.kind === edge.kind &&
      candidate.description === edge.description
    );
    const neighbor = direction === "incoming" ? edge.from : edge.to;
    const tex = edge.tex ? renderTexInline(edge.tex) : "none";
    return `<li>
      <span class="edge-route">${escapeHtml(nodeTitle(edge.from))} --${escapeHtml(edge.kind)}--&gt; ${escapeHtml(nodeTitle(edge.to))}</span>
      <p class="edge-description">${escapeHtml(edge.description)}</p>
      <div>TeX: ${tex}</div>
      <button class="edge-button" type="button" data-jump-edge="${edgeIndex}">Highlight edge</button>
      <button class="edge-button" type="button" data-jump-node="${escapeAttr(neighbor)}">Highlight ${escapeHtml(nodeTitle(neighbor))}</button>
    </li>`;
  }).join("")}</ul>`;
}

function renderTexInline(tex) {
  if (!tex.exists) {
    return `${escapeHtml(tex.file)}#${escapeHtml(tex.label)} <span class="empty">(not generated yet)</span>`;
  }
  return `<a href="${escapeAttr(tex.href)}">Rendered derivation</a> <span class="empty">${escapeHtml(tex.file)}#${escapeHtml(tex.label)}</span>`;
}

function formatLines(ref) {
  if (!ref.lineStart) return "";
  if (ref.lineStart === ref.lineEnd) return ` line ${ref.lineStart}`;
  return ` lines ${ref.lineStart}-${ref.lineEnd}`;
}

function renderMaybeLink(href, label, exists) {
  if (exists) return `<a href="${escapeAttr(href)}">${escapeHtml(label)}</a>`;
  return `${escapeHtml(label)} <span class="empty">(not generated yet)</span>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function shorten(value, maxLength) {
  const text = String(value ?? "");
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + "...";
}

function nodeTitle(nodeId) {
  const node = findNode(nodeId);
  return node ? displayName(node) : nodeId;
}

function displayName(node) {
  return node.displayLabel || node.title || node.id;
}

function renderNodeTitle(node) {
  if (node.titleImage) {
    return `<img class="inline-title-image" src="${escapeAttr(node.titleImage)}" alt="${escapeAttr(displayName(node))}">`;
  }
  return escapeHtml(displayName(node));
}
