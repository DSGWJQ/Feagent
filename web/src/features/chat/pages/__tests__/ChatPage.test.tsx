/**
 * ChatPage tests
 *
 * Contract:
 * - `/` 只能调用 /api/conversation/stream
 * - `/` 绝不调用 /api/workflows/chat-create/stream
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Route, Routes } from 'react-router-dom';
import { renderWithProviders, screen, waitFor, userEvent } from '@/test/utils';

import { ChatPage } from '../ChatPage';

function createSseReadableStream(chunks: string[]) {
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
        }, 0);
      });
    },
    cancel() {
      isClosedOrCanceled = true;
    },
  });
}

describe('ChatPage', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('posts to /api/conversation/stream and never calls chat-create', async () => {
    const body = createSseReadableStream([
      `data: ${JSON.stringify({
        type: 'final',
        content: 'ok',
        metadata: { is_final: true },
        timestamp: new Date().toISOString(),
        sequence: 1,
        is_streaming: false,
        message_id: 'm_1',
      })}\n\n`,
      'data: [DONE]\n\n',
    ]);

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body,
      headers: new Headers({ 'X-Session-ID': 'sess_test_123' }),
    } as any);

    const user = userEvent.setup();

    renderWithProviders(
      <Routes>
        <Route path="/" element={<ChatPage />} />
      </Routes>,
      { initialEntries: ['/'] }
    );

    await user.type(
      screen.getByPlaceholderText('描述你想做的事（Enter 发送，Shift+Enter 换行）'),
      'hello'
    );
    // AntD may insert whitespace between CJK characters, so match loosely.
    await user.click(screen.getByRole('button', { name: /发\s*送/ }));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalled();
    });

    const calls = (globalThis.fetch as any).mock.calls.map((args: any[]) => String(args[0]));
    expect(calls.some((url: string) => url.includes('/api/conversation/stream'))).toBe(true);
    expect(calls.some((url: string) => url.includes('/api/workflows/chat-create/stream'))).toBe(
      false
    );
  });
});
