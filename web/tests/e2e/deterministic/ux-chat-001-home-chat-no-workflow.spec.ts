/**
 * UX-CHAT-001: Home Chat (no workflow)
 *
 * Contract:
 * - Visiting `/` and sending a message must call `/api/conversation/stream`
 * - It must NOT call `/api/workflows/chat-create/stream`
 * - UI must not navigate into `/workflows/*`
 */

import { test, expect } from '../fixtures/workflowFixtures';

test.describe('UX-CHAT-001: Home Chat (no workflow)', () => {
  test('should respond via conversation stream and never create workflows', async ({ page }) => {
    test.setTimeout(60_000);

    const chatCreateRequests: string[] = [];
    const conversationRequests: string[] = [];

    page.on('request', (request) => {
      const url = request.url();
      if (url.includes('/api/workflows/chat-create/stream')) {
        chatCreateRequests.push(url);
      }
      if (url.includes('/api/conversation/stream')) {
        conversationRequests.push(url);
      }
    });

    await page.goto('/');

    const textarea = page.locator('[data-testid="conversation-textarea"]');
    await expect(textarea).toBeVisible({ timeout: 15_000 });
    await textarea.fill('我想做数据清洗：类型转换、去重、去空。你需要先问我哪些关键问题？');

    const sendButton = page.locator('[data-testid="conversation-send"]');
    await expect(sendButton).toBeEnabled();
    await sendButton.click();

    // Wait for assistant final content.
    const assistantContent = page
      .locator('[data-testid="conversation-message-content-assistant"]')
      .last();
    await expect(assistantContent).not.toHaveText('', { timeout: 30_000 });

    // Must not navigate into workflow pages.
    await expect(page).not.toHaveURL(/\/workflows\//);

    // Network-level evidence (fail-closed contract).
    expect(chatCreateRequests, `unexpected chat-create requests: ${chatCreateRequests.join(',')}`).toHaveLength(0);
    expect(conversationRequests.length).toBeGreaterThan(0);
  });
});
