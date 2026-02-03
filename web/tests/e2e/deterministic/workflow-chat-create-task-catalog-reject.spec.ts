/**
 * Deterministic UI E2E: Chat-create Task Catalog Rejects (R-01..R-10 must reject)
 *
 * Goal:
 * - Simulate real user operations (explicit create page)
 * - Verify fail-closed behavior: invalid requests/workflows are rejected at *save gate*
 *   with HTTP 400 + structured DomainValidationError details.
 *
 * NOTE:
 * - The frontend currently surfaces non-2xx as `HTTP error! status: <code>` (workflowsApi.ts).
 * - We still assert response body `detail.errors[]` to ensure correct error codes/paths.
 */

import { test, expect } from '../fixtures/workflowFixtures';
import type { Page, Response, APIRequestContext } from '@playwright/test';

type DomainValidationErrorResponse = {
  detail?: {
    code?: string;
    message?: string;
    errors?: Array<{ code?: string; message?: string; path?: string }>;
  };
};

async function apiChatCreateExpectValidationError(
  request: APIRequestContext,
  prompt: string,
): Promise<DomainValidationErrorResponse> {
  const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';

  const response = await request.post(`${apiBaseUrl}/api/workflows/chat-create/stream`, {
    data: {
      message: prompt,
      // Keep consistent with the UI contract (run_id + project_id are commonly present).
      run_id: `e2e_reject_${Date.now()}`,
      project_id: 'e2e_test_project',
    },
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      'X-Workflow-Create': 'explicit',
    },
  });

  expect(
    response.status(),
    `expected API 400 but got ${response.status()} body=${await response.text().catch(() => '')}`,
  ).toBe(400);
  return (await response.json().catch(() => ({}))) as DomainValidationErrorResponse;
}

async function chatCreateExpect400(page: Page, prompt: string): Promise<Response> {
  await page.goto('/workflows/new');

  const createTextarea = page.locator('[data-testid="workflow-chat-create-textarea"]');
  await expect(createTextarea).toBeVisible({ timeout: 15_000 });
  await createTextarea.fill(prompt);

  const createButton = page.locator('[data-testid="workflow-chat-create-submit"]');
  await expect(createButton).toBeEnabled();

  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/workflows/chat-create/stream'),
    { timeout: 30_000 },
  );

  await createButton.click();
  const response = await responsePromise;

  expect(response.status(), `expected 400 but got ${response.status()} url=${response.url()}`).toBe(400);

  // UI should stay on the create page and show the generic fetch error message.
  await expect(page.getByText('HTTP error! status: 400')).toBeVisible({ timeout: 15_000 });
  expect(page.url()).not.toMatch(/\/workflows\/[^/]+\/edit/);

  return response;
}

function expectValidationError(
  payload: DomainValidationErrorResponse,
  expected: { code: string; pathIncludes: string },
): void {
  const detail = payload.detail;
  expect(detail?.code, `unexpected error payload: ${JSON.stringify(payload)}`).toBe('workflow_invalid');

  const errors = Array.isArray(detail?.errors) ? detail?.errors ?? [] : [];
  expect(errors.length, 'expected detail.errors to be non-empty').toBeGreaterThan(0);

  const matched = errors.some(
    (err) =>
      err?.code === expected.code && String(err?.path ?? '').includes(expected.pathIncludes),
  );
  expect(
    matched,
    `expected an error with code=${expected.code} and path containing "${expected.pathIncludes}", got: ${JSON.stringify(
      errors,
    )}`,
  ).toBeTruthy();
}

test.describe('Workflow Chat-Create Task Catalog Rejects (UI, deterministic)', () => {
  test('R-01: should reject non-sqlite database_url (unsupported_database_url)', async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);

    const prompt =
      'R-01 请生成一个工作流：连接 Postgres 查询数据并写回（必须拒绝，sqlite-only）。';
    await chatCreateExpect400(page, prompt);
    const payload = await apiChatCreateExpectValidationError(request, prompt);
    expectValidationError(payload, {
      code: 'unsupported_database_url',
      pathIncludes: 'config.database_url',
    });
  });

  test('R-02: should reject non-OpenAI model/provider (unsupported_model_provider)', async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);

    const prompt = 'R-02 请用 Claude/Gemini 生成文案（必须拒绝，OpenAI-only）。';
    await chatCreateExpect400(page, prompt);
    const payload = await apiChatCreateExpectValidationError(request, prompt);
    expectValidationError(payload, { code: 'unsupported_model_provider', pathIncludes: 'config.model' });
  });

  test('R-03: should reject cycle graph (cycle_detected)', async ({ page, request }) => {
    test.setTimeout(60_000);

    const prompt = 'R-03 请生成一个会一直循环执行直到成功的工作流（必须拒绝，DAG-only）。';
    await chatCreateExpect400(page, prompt);
    const payload = await apiChatCreateExpectValidationError(request, prompt);
    expectValidationError(payload, { code: 'cycle_detected', pathIncludes: 'edges' });
  });

  test('R-04: should reject tool node missing tool_id (missing_tool_id)', async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);

    const prompt = 'R-04 请调用天气工具查询天气（但我不提供 tool_id）（必须拒绝/要求补充）。';
    await chatCreateExpect400(page, prompt);
    const payload = await apiChatCreateExpectValidationError(request, prompt);
    expectValidationError(payload, { code: 'missing_tool_id', pathIncludes: 'config.tool_id' });
  });

  test('R-05: should reject structuredOutput missing schema (missing_schema)', async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);

    const prompt = 'R-05 请抽取字段并输出 JSON（但我不提供 schema）（必须拒绝）。';
    await chatCreateExpect400(page, prompt);
    const payload = await apiChatCreateExpectValidationError(request, prompt);
    expectValidationError(payload, { code: 'missing_schema', pathIncludes: 'config.schema' });
  });

  test('R-06: should reject webhook notification missing url (missing_url)', async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);

    const prompt = 'R-06 请在流程结束后发送 webhook 通知（但我不提供 url）（必须拒绝）。';
    await chatCreateExpect400(page, prompt);
    const payload = await apiChatCreateExpectValidationError(request, prompt);
    expectValidationError(payload, { code: 'missing_url', pathIncludes: 'config.url' });
  });

  test('R-07: should reject unsupported loop semantics (unsupported_semantics)', async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);

    const prompt =
      'R-07 请遍历用户列表，逐个调用画像 API 并汇总结果（要求 loop 驱动下游节点逐条执行）（必须拒绝：当前不可表达）。';
    await chatCreateExpect400(page, prompt);
    const payload = await apiChatCreateExpectValidationError(request, prompt);
    expectValidationError(payload, { code: 'unsupported_semantics', pathIncludes: 'workflow' });
  });

  test('R-08: should reject structuredOutput schema invalid JSON (invalid_json)', async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);

    const prompt =
      "R-08 请做结构化抽取（schemaName=Ticket，schema='{'）（必须拒绝：schema 字符串非法 JSON）。";
    await chatCreateExpect400(page, prompt);
    const payload = await apiChatCreateExpectValidationError(request, prompt);
    expectValidationError(payload, { code: 'invalid_json', pathIncludes: 'config.schema' });
  });

  test('R-09: should reject slack notification missing webhook_url (missing_webhook_url)', async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);

    const prompt = 'R-09 请在流程结束后发送 Slack 通知（但我不提供 webhook_url）（必须拒绝）。';
    await chatCreateExpect400(page, prompt);
    const payload = await apiChatCreateExpectValidationError(request, prompt);
    expectValidationError(payload, { code: 'missing_webhook_url', pathIncludes: 'config.webhook_url' });
  });

  test('R-10: should reject email notification missing smtp_host (missing_smtp_host)', async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);

    const prompt = 'R-10 请在流程结束后发送 email 通知（但我不提供 smtp_host）（必须拒绝）。';
    await chatCreateExpect400(page, prompt);
    const payload = await apiChatCreateExpectValidationError(request, prompt);
    expectValidationError(payload, { code: 'missing_smtp_host', pathIncludes: 'config.smtp_host' });
  });
});
