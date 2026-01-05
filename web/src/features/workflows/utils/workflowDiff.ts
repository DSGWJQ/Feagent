import type { WorkflowEdge, WorkflowNode } from '../types/workflow';

export type DiffKind = 'added' | 'deleted' | 'updated';

export interface DiffItem {
  kind: DiffKind;
  id: string;
  fields?: string[];
}

export interface DiffCounts {
  added: number;
  deleted: number;
  updated: number;
}

export interface WorkflowDiffSummary {
  nodes: DiffCounts;
  edges: DiffCounts;
  nodeChanges: DiffItem[];
  edgeChanges: DiffItem[];
}

function safeStableStringify(value: unknown): string {
  const seen = new WeakSet<object>();
  const stringify = (v: unknown): unknown => {
    if (v && typeof v === 'object') {
      if (seen.has(v as object)) return '[Circular]';
      seen.add(v as object);
      if (Array.isArray(v)) return v.map(stringify);
      const obj = v as Record<string, unknown>;
      const out: Record<string, unknown> = {};
      Object.keys(obj)
        .sort()
        .forEach((k) => {
          out[k] = stringify(obj[k]);
        });
      return out;
    }
    return v;
  };
  try {
    return JSON.stringify(stringify(value));
  } catch {
    return String(value);
  }
}

function isEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  return safeStableStringify(a) === safeStableStringify(b);
}

function diffNodeFields(before: WorkflowNode, after: WorkflowNode): string[] {
  const fields: string[] = [];

  if (!isEqual(before.type, after.type)) fields.push('type');

  const bp = before.position;
  const ap = after.position;
  if ((bp?.x ?? 0) !== (ap?.x ?? 0) || (bp?.y ?? 0) !== (ap?.y ?? 0)) fields.push('position');

  const bd = (before.data ?? {}) as Record<string, unknown>;
  const ad = (after.data ?? {}) as Record<string, unknown>;
  const keys = new Set([...Object.keys(bd), ...Object.keys(ad)]);
  for (const key of Array.from(keys).sort()) {
    if (!isEqual(bd[key], ad[key])) fields.push(`data.${key}`);
  }

  return fields;
}

function diffEdgeFields(before: WorkflowEdge, after: WorkflowEdge): string[] {
  const fields: string[] = [];
  const pairs: Array<[keyof WorkflowEdge, string]> = [
    ['source', 'source'],
    ['target', 'target'],
    ['sourceHandle', 'sourceHandle'],
    ['label', 'label'],
    ['condition', 'condition'],
  ];
  for (const [key, label] of pairs) {
    if (!isEqual(before[key], after[key])) fields.push(label);
  }
  return fields;
}

export function diffWorkflowGraphs(
  baseline: { nodes: WorkflowNode[]; edges: WorkflowEdge[] },
  next: { nodes: WorkflowNode[]; edges: WorkflowEdge[] }
): WorkflowDiffSummary {
  const baseNodes = new Map((baseline.nodes ?? []).map((n) => [n.id, n]));
  const nextNodes = new Map((next.nodes ?? []).map((n) => [n.id, n]));

  const nodeChanges: DiffItem[] = [];
  for (const [id, node] of nextNodes) {
    const before = baseNodes.get(id);
    if (!before) {
      nodeChanges.push({ kind: 'added', id });
      continue;
    }
    const fields = diffNodeFields(before, node);
    if (fields.length) nodeChanges.push({ kind: 'updated', id, fields });
  }
  for (const [id] of baseNodes) {
    if (!nextNodes.has(id)) nodeChanges.push({ kind: 'deleted', id });
  }

  const baseEdges = new Map((baseline.edges ?? []).map((e) => [e.id, e]));
  const nextEdges = new Map((next.edges ?? []).map((e) => [e.id, e]));

  const edgeChanges: DiffItem[] = [];
  for (const [id, edge] of nextEdges) {
    const before = baseEdges.get(id);
    if (!before) {
      edgeChanges.push({ kind: 'added', id });
      continue;
    }
    const fields = diffEdgeFields(before, edge);
    if (fields.length) edgeChanges.push({ kind: 'updated', id, fields });
  }
  for (const [id] of baseEdges) {
    if (!nextEdges.has(id)) edgeChanges.push({ kind: 'deleted', id });
  }

  const count = (items: DiffItem[], kind: DiffKind) => items.filter((i) => i.kind === kind).length;

  return {
    nodes: {
      added: count(nodeChanges, 'added'),
      deleted: count(nodeChanges, 'deleted'),
      updated: count(nodeChanges, 'updated'),
    },
    edges: {
      added: count(edgeChanges, 'added'),
      deleted: count(edgeChanges, 'deleted'),
      updated: count(edgeChanges, 'updated'),
    },
    nodeChanges,
    edgeChanges,
  };
}
