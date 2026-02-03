/**
 * UX-WF-CLEAN-001: Chat-create Data Cleaning Workflow (real execution output)
 *
 * Acceptance:
 * - Create workflow via POST /api/workflows/chat-create/stream (SSE)
 * - Execute workflow via POST /api/workflows/{workflow_id}/execute/stream (SSE)
 * - Assert final workflow output includes: type conversion + dedupe + drop-empty
 *
 * Test Mode: Deterministic
 */

import { test, expect } from '../fixtures/workflowFixtures';

function parseSseJsonEvents(text: string): any[] {
  const events: any[] = [];
  for (const line of text.split('\n')) {
    if (!line.startsWith('data: ')) continue;
    const payload = line.slice('data: '.length).trim();
    if (!payload || payload === '[DONE]') continue;
    events.push(JSON.parse(payload));
  }
  return events;
}

test.describe('UX-WF-CLEAN-001: Chat-create Data Cleaning Workflow', () => {
  test('should create cleaning workflow via chat-create and execute to produce expected output', async ({
    page,
    cleanupTokens,
  }) => {
    test.setTimeout(60_000);

    const baseURL = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
    const projectId = 'e2e_cleaning_project';

    const chatCreateMessage =
      '请通过 Chat-create 创建一个“数据清洗”工作流：类型转换、去重、去空。输入数据在 initial_input.data 数组里，输出清洗后的 data。';

    const chatCreateResp = await page.request.post(`${baseURL}/api/workflows/chat-create/stream`, {
      data: {
        message: chatCreateMessage,
        project_id: projectId,
      },
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        'X-Workflow-Create': 'explicit',
      },
      timeout: 60_000,
    });

    const chatCreateText = await chatCreateResp.text();
    expect(
      chatCreateResp.ok(),
      `chat-create failed: HTTP ${chatCreateResp.status()} body=${chatCreateText}`,
    ).toBeTruthy();

    const chatEvents = parseSseJsonEvents(chatCreateText);
    expect(chatEvents.length).toBeGreaterThan(0);

    const workflowId = chatEvents[0]?.metadata?.workflow_id;
    expect(workflowId, `missing metadata.workflow_id in first SSE event: ${chatCreateText}`).toBeTruthy();

    // Ensure cleanup runs after test (same semantics as Seed API tokens).
    cleanupTokens.push(`cleanup_${workflowId}`);

    // Create run (required by execute/stream)
    const runResp = await page.request.post(
      `${baseURL}/api/projects/${projectId}/workflows/${workflowId}/runs`,
      {
        data: {},
        headers: { 'Content-Type': 'application/json' },
        timeout: 10_000,
      },
    );
    const runJson = await runResp.json();
    expect(runResp.ok(), `create run failed: HTTP ${runResp.status()} body=${JSON.stringify(runJson)}`).toBeTruthy();
    const runId = runJson?.id;
    expect(runId, `missing run id: body=${JSON.stringify(runJson)}`).toBeTruthy();

    const initialInput = {
      data: [
        { user_id: '1', age: '20', email: 'a@example.com' },
        { user_id: '1', age: '20', email: 'a@example.com' }, // duplicate row
        { user_id: '', age: null, email: '   ' }, // empty row (should be dropped)
        { user_id: '2', age: '30', email: 'b@example.com' },
      ],
    };

    const executeResp = await page.request.post(`${baseURL}/api/workflows/${workflowId}/execute/stream`, {
      data: {
        run_id: runId,
        initial_input: initialInput,
      },
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      timeout: 30_000,
    });

    const executeText = await executeResp.text();
    expect(
      executeResp.ok(),
      `execute/stream failed: HTTP ${executeResp.status()} body=${executeText}`,
    ).toBeTruthy();

    const execEvents = parseSseJsonEvents(executeText);
    const workflowComplete = execEvents.find((e) => e?.type === 'workflow_complete');
    expect(workflowComplete, `missing workflow_complete event: ${executeText}`).toBeTruthy();

    expect(workflowComplete.result).toEqual({
      data: [
        { user_id: 1, age: 20, email: 'a@example.com' },
        { user_id: 2, age: 30, email: 'b@example.com' },
      ],
    });
  });
});
