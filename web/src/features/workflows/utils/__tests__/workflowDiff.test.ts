import { describe, expect, it } from 'vitest';
import { diffWorkflowGraphs } from '../workflowDiff';

describe('diffWorkflowGraphs', () => {
  it('counts node add/delete/update', () => {
    const baseline = {
      nodes: [
        { id: 'n1', type: 'start', position: { x: 0, y: 0 }, data: { name: 'A' } },
        { id: 'n2', type: 'tool', position: { x: 1, y: 0 }, data: { tool_id: 't1' } },
      ],
      edges: [],
    };
    const next = {
      nodes: [
        { id: 'n2', type: 'tool', position: { x: 1, y: 0 }, data: { tool_id: 't2' } }, // updated
        { id: 'n3', type: 'end', position: { x: 2, y: 0 }, data: {} }, // added
      ],
      edges: [],
    };

    const summary = diffWorkflowGraphs(baseline as any, next as any);
    expect(summary.nodes.added).toBe(1);
    expect(summary.nodes.deleted).toBe(1);
    expect(summary.nodes.updated).toBe(1);
    expect(summary.nodeChanges.find((c) => c.id === 'n2')?.fields).toContain('data.tool_id');
  });

  it('is tolerant to unknown nested fields', () => {
    const baseline = {
      nodes: [{ id: 'n1', type: 'httpRequest', position: { x: 0, y: 0 }, data: { meta: { a: 1 } } }],
      edges: [],
    };
    const next = {
      nodes: [{ id: 'n1', type: 'httpRequest', position: { x: 0, y: 0 }, data: { meta: { a: 2 } } }],
      edges: [],
    };

    const summary = diffWorkflowGraphs(baseline as any, next as any);
    expect(summary.nodes.updated).toBe(1);
  });
});
