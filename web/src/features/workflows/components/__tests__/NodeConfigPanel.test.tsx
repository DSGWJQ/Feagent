import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { createTestQueryClient, renderWithProviders, screen, userEvent, waitFor } from '@/test/utils';

import NodeConfigPanel from '../NodeConfigPanel';

const mockCapabilities = {
  schema_version: 'test/v1',
  constraints: {
    sqlite_only: true,
    sqlite_database_url_prefix: 'sqlite:///',
    model_providers_supported: ['openai'],
    openai_only: true,
    draft_validation_scope: 'main_subgraph_only',
  },
  node_types: [
    {
      type: 'textModel',
      aliases: ['llm'],
      executor_available: true,
      runtime_notes: [],
      validation_contract: {
        required_fields: [
          {
            key: 'model',
            kind: 'string',
            code: 'missing_model',
            message: 'model is required for textModel nodes',
            path: 'config.model',
          },
        ],
        required_any_of: [],
        enum_fields: [
          {
            key: 'model',
            allowed: ['openai/gpt-5', 'openai/gpt-4'],
            code: 'unsupported_model',
            message: 'unsupported textModel model: {value}',
            path: 'config.model',
            normalize: 'strip',
            meta: {
              labels: {
                'openai/gpt-5': 'OpenAI GPT-5',
                'openai/gpt-4': 'OpenAI GPT-4',
              },
            },
          },
        ],
        json_fields: [],
        conditional_required: [],
      },
    },
    {
      type: 'imageGeneration',
      aliases: [],
      executor_available: true,
      runtime_notes: [],
      validation_contract: {
        required_fields: [
          {
            key: 'model',
            kind: 'string',
            code: 'missing_model',
            message: 'model is required for image nodes',
            path: 'config.model',
          },
        ],
        required_any_of: [],
        enum_fields: [
          {
            key: 'model',
            allowed: ['openai/dall-e-3'],
            code: 'unsupported_model',
            message: 'unsupported imageGeneration model: {value}',
            path: 'config.model',
            normalize: 'strip',
            meta: {
              labels: {
                'openai/dall-e-3': 'DALL-E 3',
              },
            },
          },
        ],
        json_fields: [],
        conditional_required: [],
      },
    },
  ],
};

describe('NodeConfigPanel', () => {
  it('textModel model select only exposes OpenAI options (no anthropic/google)', async () => {
    const user = userEvent.setup();
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(['workflows', 'capabilities'], mockCapabilities);

    renderWithProviders(
      <NodeConfigPanel
        open={true}
        node={
          {
            id: 'node_textModel',
            type: 'textModel',
            data: { model: 'openai/gpt-5' },
            position: { x: 0, y: 0 },
          } as any
        }
        nodes={[]}
        edges={[]}
        onClose={() => {}}
        onSave={() => {}}
      />,
      { queryClient }
    );

    const combobox = screen.getByRole('combobox');
    await user.click(combobox);

    // AntD Select renders the selected value and the dropdown option with the same text.
    // Assert against option roles to avoid ambiguous matches.
    expect(screen.getByRole('option', { name: 'OpenAI GPT-5' })).toBeInTheDocument();
    expect(
      screen.queryByRole('option', { name: 'Claude 3.5 Sonnet' })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('option', { name: 'Gemini 2.5 Flash' })
    ).not.toBeInTheDocument();
  });

  it('fails closed when textModel has a model value not in enum', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(['workflows', 'capabilities'], mockCapabilities);

    renderWithProviders(
      <NodeConfigPanel
        open={true}
        node={
          {
            id: 'node_textModel',
            type: 'textModel',
            data: { model: 'openai/gpt-4o-mini' },
            position: { x: 0, y: 0 },
          } as any
        }
        nodes={[]}
        edges={[]}
        onClose={() => {}}
        onSave={onSave}
      />,
      { queryClient }
    );

    await waitFor(() =>
      expect(screen.getByText('Unsupported model value')).toBeInTheDocument()
    );

    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    expect(onSave).not.toHaveBeenCalled();
    expect(
      await screen.findByText(/unsupported textModel model: openai\/gpt-4o-mini/i)
    ).toBeInTheDocument();
  });

  it('imageGeneration model select does not expose Gemini option', async () => {
    const user = userEvent.setup();
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(['workflows', 'capabilities'], mockCapabilities);

    renderWithProviders(
      <NodeConfigPanel
        open={true}
        node={
          {
            id: 'node_imageGeneration',
            type: 'imageGeneration',
            data: { model: 'openai/dall-e-3' },
            position: { x: 0, y: 0 },
          } as any
        }
        nodes={[]}
        edges={[]}
        onClose={() => {}}
        onSave={() => {}}
      />,
      { queryClient }
    );

    const comboboxes = screen.getAllByRole('combobox');
    await user.click(comboboxes[0]);

    expect(screen.getByRole('option', { name: 'DALL-E 3' })).toBeInTheDocument();
    expect(
      screen.queryByRole('option', { name: 'Gemini 2.5 Flash Image' })
    ).not.toBeInTheDocument();
  });

  it('textModel with multiple incoming edges requires promptSourceNodeId', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(['workflows', 'capabilities'], mockCapabilities);

    const { rerender } = renderWithProviders(
      <NodeConfigPanel
        open={true}
        node={
          {
            id: 'node_llm',
            type: 'textModel',
            data: { model: 'openai/gpt-5' },
            position: { x: 0, y: 0 },
          } as any
        }
        nodes={
          [
            { id: 'node_a', type: 'httpRequest', data: {}, position: { x: 0, y: 0 } },
            { id: 'node_b', type: 'prompt', data: {}, position: { x: 0, y: 0 } },
            {
              id: 'node_llm',
              type: 'textModel',
              data: { model: 'openai/gpt-5' },
              position: { x: 0, y: 0 },
            },
          ] as any
        }
        edges={
          [
            { id: 'e1', source: 'node_a', target: 'node_llm' },
            { id: 'e2', source: 'node_b', target: 'node_llm' },
          ] as any
        }
        onClose={() => {}}
        onSave={onSave}
      />,
      { queryClient }
    );

    expect(screen.getByText('Prompt Source')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Save Changes' }));
    expect(await screen.findByText('Please select prompt source node')).toBeInTheDocument();
    expect(screen.queryByText('Please select model')).not.toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();

    // Re-render with the required field set (this avoids flakey DOM interactions with AntD Select).
    rerender(
      <NodeConfigPanel
        open={true}
        node={
          {
            id: 'node_llm',
            type: 'textModel',
            data: { model: 'openai/gpt-5', promptSourceNodeId: 'node_a' },
            position: { x: 0, y: 0 },
          } as any
        }
        nodes={
          [
            { id: 'node_a', type: 'httpRequest', data: {}, position: { x: 0, y: 0 } },
            { id: 'node_b', type: 'prompt', data: {}, position: { x: 0, y: 0 } },
            {
              id: 'node_llm',
              type: 'textModel',
              data: { model: 'openai/gpt-5', promptSourceNodeId: 'node_a' },
              position: { x: 0, y: 0 },
            },
          ] as any
        }
        edges={
          [
            { id: 'e1', source: 'node_a', target: 'node_llm' },
            { id: 'e2', source: 'node_b', target: 'node_llm' },
          ] as any
        }
        onClose={() => {}}
        onSave={onSave}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        'node_llm',
        expect.objectContaining({ promptSourceNodeId: 'node_a' })
      )
    );
  });
});
