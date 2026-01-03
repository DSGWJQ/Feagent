import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useRunReplay } from '../useRunReplay';

vi.mock('@/services/api', () => ({
  API_BASE_URL: '/api',
}));

describe('useRunReplay', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('paginates through replay events and emits them in order', async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          run_id: 'run_1',
          events: [
            { type: 'node_start', run_id: 'run_1', node_id: 'n1' },
            { type: 'node_complete', run_id: 'run_1', node_id: 'n1', output: { ok: true } },
          ],
          next_cursor: 2,
          has_more: true,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          run_id: 'run_1',
          events: [{ type: 'workflow_complete', run_id: 'run_1', result: { ok: true } }],
          next_cursor: null,
          has_more: false,
        }),
      }) as any;

    const onEvent = vi.fn();
    const onComplete = vi.fn();
    const onError = vi.fn();

    const { result } = renderHook(() =>
      useRunReplay({
        runId: 'run_1',
        pageSize: 2,
        onEvent,
        onComplete,
        onError,
      })
    );

    await act(async () => {
      await result.current.startReplay();
    });

    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
    expect(onEvent).toHaveBeenCalledTimes(3);
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
    expect(result.current.isReplaying).toBe(false);
  });

  it('stopReplay aborts an in-flight replay without raising onError', async () => {
    globalThis.fetch = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('Aborted', 'AbortError'));
        });
      });
    }) as any;

    const onError = vi.fn();
    const { result } = renderHook(() =>
      useRunReplay({
        runId: 'run_1',
        onError,
      })
    );

    act(() => {
      void result.current.startReplay();
    });

    await act(async () => {
      result.current.stopReplay();
    });

    expect(onError).not.toHaveBeenCalled();
    expect(result.current.isReplaying).toBe(false);
  });
});
