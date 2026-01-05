import React, { useMemo } from 'react';
import type { WorkflowDiffSummary } from '../utils/workflowDiff';

export interface WorkflowDiffSummaryProps {
  summary: WorkflowDiffSummary;
  maxItems?: number;
}

function formatFields(fields: string[] | undefined): string {
  if (!fields || fields.length === 0) return '';
  const shown = fields.slice(0, 6);
  const tail = fields.length > shown.length ? ` (+${fields.length - shown.length})` : '';
  return `: ${shown.join(', ')}${tail}`;
}

export function WorkflowDiffSummaryView({ summary, maxItems = 6 }: WorkflowDiffSummaryProps) {
  const items = useMemo(() => {
    const all = [
      ...summary.nodeChanges.map((c) => ({ scope: 'node' as const, ...c })),
      ...summary.edgeChanges.map((c) => ({ scope: 'edge' as const, ...c })),
    ];
    return all.slice(0, maxItems);
  }, [summary, maxItems]);

  return (
    <div>
      <div style={{ fontSize: 12, color: '#555' }}>
        Nodes: +{summary.nodes.added} -{summary.nodes.deleted} ~{summary.nodes.updated} · Edges: +
        {summary.edges.added} -{summary.edges.deleted} ~{summary.edges.updated}
      </div>

      {items.length > 0 && (
        <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: 12 }}>
          {items.map((it) => (
            <li key={`${it.scope}:${it.id}`}>
              {it.scope} {it.kind} {it.id}
              {formatFields(it.fields)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default WorkflowDiffSummaryView;
