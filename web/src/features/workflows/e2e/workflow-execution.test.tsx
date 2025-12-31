/**
 * Workflow streaming integration tests (Vitest)
 *
 * 目标：覆盖 workflow 关键流式调用（chat-stream / execute/stream）的 SSE 解析逻辑，
 * 避免在 API client 收敛后出现回归（404/解析失败/不触发回调）。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { waitFor } from '@testing-library/react';
import {
  chatWorkflowStreaming,
  executeWorkflowStreaming,
} from '../api/workflowsApi';

function createSseReadableStream(chunks: string[], intervalMs = 0) {
  const encoder = new TextEncoder();
  let isClosedOrCanceled = false;
  return new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk, index) => {
        setTimeout(() => {
          if (isClosedOrCanceled) return;
          controller.enqueue(encoder.encode(chunk));
          if (index === chunks.length - 1) {
            isClosedOrCanceled = true;
            controller.close();
          }
        }, index * intervalMs);
      });
    },
    cancel() {
      isClosedOrCanceled = true;
    },
  });
}

describe('workflow streaming SSE parsing', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('chatWorkflowStreaming parses JSON events from `data:` chunks', async () => {
    const onEvent = vi.fn();
    const onError = vi.fn();

    const body = createSseReadableStream(
      [
        'data: {"type":"thinking","content":"AI 正在分析...","is_final":false}\n\n',
        'data: {"type":"final","content":"完成","is_final":true}\n\n',
      ],
      0
    );

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body,
    } as any);

    chatWorkflowStreaming('wf_test_123', { message: 'hello' }, onEvent, onError);

    await waitFor(() => {
      expect(onError).not.toHaveBeenCalled();
      expect(onEvent).toHaveBeenCalledTimes(2);
      expect(onEvent).toHaveBeenNthCalledWith(1, expect.objectContaining({ type: 'thinking' }));
      expect(onEvent).toHaveBeenNthCalledWith(2, expect.objectContaining({ type: 'final' }));
    });
  });

  it('executeWorkflowStreaming parses `data: ` lines and stops on workflow_complete', async () => {
    const onEvent = vi.fn();
    const onError = vi.fn();

    const body = createSseReadableStream(
      [
        'data: {"type":"node_start","node_id":"1"}\n',
        'data: {"type":"workflow_complete","result":{"success":true}}\n',
        // should not be observed if reader.cancel() stops the loop
        'data: {"type":"node_start","node_id":"SHOULD_NOT_HAPPEN"}\n',
      ],
      0
    );

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body,
    } as any);

    executeWorkflowStreaming('wf_test_123', { inputs: {} } as any, onEvent, onError);

    await waitFor(() => {
      expect(onError).not.toHaveBeenCalled();
      expect(onEvent).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'node_start', node_id: '1' })
      );
      expect(onEvent).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'workflow_complete' })
      );
      expect(onEvent).not.toHaveBeenCalledWith(
        expect.objectContaining({ node_id: 'SHOULD_NOT_HAPPEN' })
      );
    });
  });
});
