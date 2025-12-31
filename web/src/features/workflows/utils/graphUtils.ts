import type { Edge } from '@xyflow/react';

export function wouldCreateCycle(edges: Edge[], source: string, target: string): boolean {
  if (source === target) return true;

  const adjacency = new Map<string, string[]>();
  for (const edge of edges) {
    const next = adjacency.get(edge.source);
    if (next) {
      next.push(edge.target);
    } else {
      adjacency.set(edge.source, [edge.target]);
    }
  }

  const next = adjacency.get(source);
  if (next) {
    next.push(target);
  } else {
    adjacency.set(source, [target]);
  }

  const visited = new Set<string>();
  const stack: string[] = [target];

  while (stack.length > 0) {
    const current = stack.pop();
    if (!current) continue;
    if (current === source) return true;
    if (visited.has(current)) continue;
    visited.add(current);
    const neighbors = adjacency.get(current);
    if (!neighbors) continue;
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) stack.push(neighbor);
    }
  }

  return false;
}
