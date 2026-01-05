import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { WorkflowDiffSummaryView } from '../WorkflowDiffSummary';

describe('WorkflowDiffSummaryView', () => {
  it('renders counts and change items', () => {
    render(
      <WorkflowDiffSummaryView
        summary={{
          nodes: { added: 1, deleted: 2, updated: 3 },
          edges: { added: 0, deleted: 1, updated: 0 },
          nodeChanges: [{ kind: 'updated', id: 'n1', fields: ['type', 'data.name'] }],
          edgeChanges: [{ kind: 'deleted', id: 'e1' }],
        }}
      />
    );

    expect(screen.getByText(/Nodes: \+1 -2 ~3/)).toBeInTheDocument();
    expect(screen.getByText(/Edges: \+0 -1 ~0/)).toBeInTheDocument();
    expect(screen.getByText(/node updated n1/)).toBeInTheDocument();
    expect(screen.getByText(/data\.name/)).toBeInTheDocument();
    expect(screen.getByText(/edge deleted e1/)).toBeInTheDocument();
  });
});
