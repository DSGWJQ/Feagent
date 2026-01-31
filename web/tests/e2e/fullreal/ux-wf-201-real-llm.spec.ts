/**
 * UX-WF-201: Full-real Mode E2E Tests with Real LLM
 *
 * Test Scenarios:
 * 1. Real LLM modifies workflow via /chat (rename + code update)
 * 2. Real LLM attempts to modify isolated node (rejected or safely refused)
 *
 * Priority: P1
 * Test Mode: Full-real (uses actual OpenAI API)
 *
 * Environment Requirements:
 * - OPENAI_API_KEY must be set
 * - Backend running with LLM_ADAPTER=openai, HTTP_ADAPTER=httpx
 * - E2E_TEST_MODE=fullreal
 *
 * Notes:
 * - These tests intentionally focus on LLM-backed /chat behavior (not pure workflow execution),
 *   because running a python/http-only workflow does not necessarily exercise the LLM adapter.
 * - Failures attach structured diagnostics (workflow snapshots + chat responses) for replay/debugging.
 */

import type { TestInfo } from '@playwright/test';
import { test, expect } from '../fixtures/workflowFixtures';

const RUN_LEGACY_FULLREAL_EXECUTION_TESTS =
  process.env.RUN_LEGACY_FULLREAL_EXECUTION_TESTS === 'true';

if (RUN_LEGACY_FULLREAL_EXECUTION_TESTS) {
  test.describe('UX-WF-201: Full-real Mode - Legacy execution tests (disabled by default)', () => {
  /**
   * UX-WF-201: Run simple workflow with real LLM
   *
   * This test uses actual OpenAI API to execute a workflow.
   * Cost: ~$0.001-0.01 per run (depending on model and usage)
   *
   * Test Flow:
   * 1. Seed simple workflow (main_subgraph_only)
   * 2. Navigate to editor
   * 3. Click RUN button
   * 4. Wait for real LLM execution (may take 30-120 seconds)
   * 5. Verify completion and log run_id for replay debugging
   */
  test('should successfully execute workflow with real LLM', async ({
    page,
    seedWorkflow,
  }) => {
    let workflowId: string | undefined;
    const runId: string | null = null;

    try {
      // 1. Create test workflow using seed fixture
      const seedResponse = await seedWorkflow({
        fixtureType: 'main_subgraph_only',
        projectId: 'e2e_fullreal_simple',
        customMetadata: {
          test_case: 'ux-wf-201',
          description: 'Simple workflow with real LLM',
        },
      });

      workflowId = seedResponse.workflow_id;
      console.log(`[UX-WF-201] Created workflow: ${workflowId}`);

      // 2. Navigate to workflow editor
      await page.goto(`/workflows/${workflowId}/edit`);

      // 3. Wait for editor to load (canvas visible)
      await page.waitForSelector('[data-testid="workflow-canvas"]', {
        state: 'visible',
        timeout: 20000,
      });

      console.log('[UX-WF-201] Editor loaded successfully');

      // 4. Setup network listeners to capture run_id
      page.on('response', async (response) => {
        const url = response.url();

        // Capture run_id from POST /runs response
        if (url.includes('/runs') && response.request().method() === 'POST' && !url.includes('/execute')) {
          try {
            const responseStatus = response.status();
            if (responseStatus >= 200 && responseStatus < 300) {
              const data = await response.json();
              if (data.id) {
                runId = data.id;
                console.log(`[UX-WF-201] Captured run_id: ${runId}`);
              }
            }
          } catch (error) {
            console.error('[UX-WF-201] Failed to parse run creation response:', error);
          }
        }
      });

      // 5. Verify initial status is 'idle'
      const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
      await expect(statusIndicator).toHaveAttribute('data-status', 'idle', { timeout: 5000 });

      // 6. Click RUN button
      const runButton = page.locator('[data-testid="workflow-run-button"]');
      await runButton.waitFor({ state: 'visible', timeout: 5000 });
      await expect(runButton).toBeEnabled();

      console.log('[UX-WF-201] Clicking RUN button - Real LLM execution starting');
      await runButton.click();

      // 7. Verify status transitions to 'running'
      await expect(async () => {
        const status = await statusIndicator.getAttribute('data-status');
        expect(status).toBe('running');
      }).toPass({ timeout: 15000 });

      console.log('[UX-WF-201] Execution started (status: running) - Waiting for real LLM response...');

      // 8. Wait for execution to complete
      // Real LLM calls can take 30-120 seconds depending on complexity
      await expect(async () => {
        const status = await statusIndicator.getAttribute('data-status');
        expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
      }).toPass({ timeout: 120000 }); // 120 second timeout for real LLM

      const finalStatus = await statusIndicator.getAttribute('data-status');
      console.log(`[UX-WF-201] Final status: ${finalStatus}`);

      // 9. Wait for network responses to be captured
      await page.waitForTimeout(2000);

      // 10. Verify run_id was created
      expect(runId).toBeTruthy();
      console.log(`[UX-WF-201] ✓ Run completed successfully with run_id: ${runId}`);

      // 11. Log replay information for debugging
      console.log(`[UX-WF-201] Replay Info: workflow_id=${workflowId}, run_id=${runId}`);
      console.log(`[UX-WF-201] To replay: GET /api/workflows/${workflowId}/runs/${runId}/events`);

      // 12. Verify final state
      expect(finalStatus).toBeDefined();
      expect(['completed', 'idle'].includes(finalStatus ?? '')).toBeTruthy();

    } catch (error) {
      // Enhanced error handling for debugging
      console.error('[UX-WF-201] Test failed:', error);
      console.error(`[UX-WF-201] Debug Info: workflow_id=${workflowId}, run_id=${runId}`);

      // Take screenshot on failure
      await page.screenshot({
        path: `test-results/ux-wf-201-failure-${Date.now()}.png`,
        fullPage: true,
      });

      // Re-throw to fail the test
      throw error;
    }
  });

  /**
   * UX-WF-202: Run side_effect workflow with real LLM
   *
   * This test verifies the side-effect confirmation flow with real LLM.
   * The workflow contains nodes that trigger external actions (HTTP, DATABASE, etc.)
   *
   * Test Flow:
   * 1. Seed side_effect_workflow
   * 2. Navigate to editor
   * 3. Click RUN button
   * 4. Wait for side-effect confirmation modal
   * 5. Click ALLOW button
   * 6. Wait for real LLM execution completion
   * 7. Verify success and log run_id
   */
  test('should handle side-effect confirmation with real LLM', async ({
    page,
    seedWorkflow,
  }) => {
    let workflowId: string | undefined;
    const runId: string | null = null;
    let confirmId: string | null = null;

    try {
      // 1. Create side-effect workflow
      const seedResponse = await seedWorkflow({
        fixtureType: 'side_effect_workflow',
        projectId: 'e2e_fullreal_sideeffect',
        customMetadata: {
          test_case: 'ux-wf-202',
          description: 'Side-effect workflow with real LLM',
        },
      });

      workflowId = seedResponse.workflow_id;
      console.log(`[UX-WF-202] Created side-effect workflow: ${workflowId}`);

      // 2. Navigate to editor
      await page.goto(`/workflows/${workflowId}/edit`);
      await page.waitForSelector('[data-testid="workflow-canvas"]', {
        state: 'visible',
        timeout: 20000,
      });

      console.log('[UX-WF-202] Editor loaded');

      // 3. Setup network listeners
      page.on('response', async (response) => {
        const url = response.url();

        // Capture run_id
        if (url.includes('/runs') && response.request().method() === 'POST' && !url.includes('/execute')) {
          try {
            const data = await response.json();
            if (data.id) {
              runId = data.id;
              console.log(`[UX-WF-202] Captured run_id: ${runId}`);
            }
          } catch (error) {
            console.error('[UX-WF-202] Failed to parse run response:', error);
          }
        }

        // Capture confirm_id from side-effect-request event
        if (url.includes('/execute/stream')) {
          // The confirm_id will be in the SSE event stream
          // We'll extract it from the modal when it appears
          console.log('[UX-WF-202] Execute stream started');
        }
      });

      // 4. Click RUN button
      const runButton = page.locator('[data-testid="workflow-run-button"]');
      await runButton.waitFor({ state: 'visible', timeout: 5000 });
      await runButton.click();

      console.log('[UX-WF-202] RUN clicked - Waiting for side-effect confirmation modal');

      // 5. Wait for side-effect confirmation modal to appear
      const confirmModal = page.locator('[data-testid="side-effect-confirm-modal"]');
      await confirmModal.waitFor({ state: 'visible', timeout: 30000 });

      console.log('[UX-WF-202] Side-effect confirmation modal appeared');

      // 6. Extract confirm_id from hidden field
      const confirmIdField = page.locator('[data-testid="confirm-id-hidden"]');
      confirmId = await confirmIdField.getAttribute('value');
      console.log(`[UX-WF-202] Captured confirm_id: ${confirmId}`);

      // 7. Click ALLOW button
      const allowButton = page.locator('[data-testid="confirm-allow-button"]');
      await allowButton.waitFor({ state: 'visible', timeout: 5000 });
      await expect(allowButton).toBeEnabled();

      console.log('[UX-WF-202] Clicking ALLOW button');
      await allowButton.click();

      // 8. Verify modal closes
      await expect(confirmModal).not.toBeVisible({ timeout: 10000 });
      console.log('[UX-WF-202] Confirmation accepted, modal closed');

      // 9. Wait for execution to complete with real LLM
      const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
      await expect(async () => {
        const status = await statusIndicator.getAttribute('data-status');
        expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
      }).toPass({ timeout: 120000 }); // 120 second timeout

      const finalStatus = await statusIndicator.getAttribute('data-status');
      console.log(`[UX-WF-202] Final status: ${finalStatus}`);

      // 10. Verify completion
      expect(runId).toBeTruthy();
      expect(confirmId).toBeTruthy();
      console.log(`[UX-WF-202] ✓ Side-effect workflow completed: run_id=${runId}, confirm_id=${confirmId}`);

      // 11. Log replay information
      console.log(`[UX-WF-202] Replay Info: workflow_id=${workflowId}, run_id=${runId}`);
      console.log(`[UX-WF-202] To replay: GET /api/workflows/${workflowId}/runs/${runId}/events`);

    } catch (error) {
      console.error('[UX-WF-202] Test failed:', error);
      console.error(`[UX-WF-202] Debug Info: workflow_id=${workflowId}, run_id=${runId}, confirm_id=${confirmId}`);

      // Take screenshot
      await page.screenshot({
        path: `test-results/ux-wf-202-failure-${Date.now()}.png`,
        fullPage: true,
      });

      throw error;
    }
  });

  /**
   * UX-WF-203: Verify real LLM error handling
   *
   * This test intentionally triggers an error to verify error handling
   * with real LLM (e.g., invalid API key, rate limit, timeout)
   *
   * Note: This test is skipped by default to avoid API costs.
   * Enable with: npx playwright test --grep @error-handling
   */
  test.skip('should handle real LLM errors gracefully @error-handling', async ({
    page,
    seedWorkflow,
  }) => {
    let workflowId: string | undefined;
    const runId: string | null = null;

    try {
      // 1. Create workflow
      const seedResponse = await seedWorkflow({
        fixtureType: 'main_subgraph_only',
        projectId: 'e2e_fullreal_error',
      });

      workflowId = seedResponse.workflow_id;

      // 2. Navigate to editor
      await page.goto(`/workflows/${workflowId}/edit`);
      await page.waitForSelector('[data-testid="workflow-canvas"]', {
        state: 'visible',
        timeout: 20000,
      });

      // 3. Setup error monitoring
      const errors: string[] = [];
      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          errors.push(msg.text());
        }
      });

      // 4. Click RUN (assuming this will fail with invalid config)
      const runButton = page.locator('[data-testid="workflow-run-button"]');
      await runButton.click();

      // 5. Wait for error state
      await page.waitForTimeout(10000);

      // 6. Verify error message is displayed
      const errorMessage = page.locator('.ant-message-error');
      const hasError = (await errorMessage.count()) > 0;

      if (hasError) {
        const errorText = await errorMessage.first().textContent();
        console.log(`[UX-WF-203] Error message displayed: ${errorText}`);
      }

      // 7. Verify error logging
      console.log(`[UX-WF-203] Console errors captured: ${errors.length}`);
      console.log(`[UX-WF-203] Debug Info: workflow_id=${workflowId}, run_id=${runId}`);

    } catch (error) {
      console.error('[UX-WF-203] Test execution error:', error);
      throw error;
    }
  });
});
}

type WorkflowNode = {
  id: string;
  type: string;
  name?: string;
  data?: Record<string, unknown>;
};

type WorkflowEdge = {
  source: string;
  target: string;
};

type WorkflowResponse = {
  id: string;
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  status: string;
  created_at: string;
  updated_at: string;
};

type ChatResponse = {
  workflow: WorkflowResponse;
  ai_message: string;
  intent?: string;
  confidence?: number;
  modifications_count?: number;
  rag_sources?: unknown[];
  react_steps?: unknown[];
};

function getApiBaseUrl(): string {
  return process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
}

function summarizeWorkflow(workflow: WorkflowResponse): Record<string, unknown> {
  return {
    id: workflow.id,
    name: workflow.name,
    node_count: workflow.nodes?.length ?? 0,
    edge_count: workflow.edges?.length ?? 0,
    nodes: workflow.nodes?.map((n) => ({ id: n.id, type: n.type, name: n.name })) ?? [],
  };
}

function computeIsolatedNodeIds(workflow: WorkflowResponse): Set<string> {
  const connected = new Set<string>();
  for (const edge of workflow.edges ?? []) {
    if (edge?.source) connected.add(edge.source);
    if (edge?.target) connected.add(edge.target);
  }

  const all = new Set<string>((workflow.nodes ?? []).map((n) => n.id));
  const isolated = new Set<string>();
  for (const nodeId of all) {
    if (!connected.has(nodeId)) isolated.add(nodeId);
  }
  return isolated;
}

async function attachJson(testInfo: TestInfo, name: string, data: unknown) {
  await testInfo.attach(name, {
    body: Buffer.from(JSON.stringify(data, null, 2), 'utf-8'),
    contentType: 'application/json',
  });
}

async function attachText(testInfo: TestInfo, name: string, text: string) {
  await testInfo.attach(name, {
    body: Buffer.from(text, 'utf-8'),
    contentType: 'text/plain',
  });
}

function parseJsonOrNull(text: string): { json: any | null; error?: string } {
  try {
    return { json: JSON.parse(text) };
  } catch (e: any) {
    return { json: null, error: e?.message ? String(e.message) : 'JSON parse failed' };
  }
}

test.describe('UX-WF-201: Full-real Mode - Real LLM via /chat', () => {
  test.describe.configure({ mode: 'serial' });

  test('should update workflow via chat using real LLM (rename + code update)', async (
    { page, seedWorkflow },
    testInfo,
  ) => {
    test.skip(process.env.E2E_TEST_MODE !== 'fullreal', 'Requires E2E_TEST_MODE=fullreal');
    test.skip(!process.env.OPENAI_API_KEY, 'Requires OPENAI_API_KEY for real LLM testing');

    const apiBaseUrl = getApiBaseUrl();
    const diagnostics: Record<string, unknown> = { apiBaseUrl, workflowId: null, chatStatus: null };

    try {
      const { workflow_id } = await seedWorkflow({
        fixtureType: 'main_subgraph_only',
        projectId: 'e2e_fullreal_chat_update',
        customMetadata: { test_case: 'UX-WF-201', scenario: 'rename_and_code_update' },
      });
      diagnostics.workflowId = workflow_id;

      await page.goto(`/workflows/${workflow_id}/edit`);
      await page.waitForSelector('[data-testid="workflow-canvas"]', {
        state: 'visible',
        timeout: 20000,
      });

      const beforeResp = await page.request.get(`${apiBaseUrl}/api/workflows/${workflow_id}`);
      expect(beforeResp.ok()).toBeTruthy();
      const beforeWorkflow = (await beforeResp.json()) as WorkflowResponse;
      await attachJson(testInfo, 'workflow-before.json', summarizeWorkflow(beforeWorkflow));

      const targetNode =
        beforeWorkflow.nodes.find((n) => (n.name || '').trim() === 'Process Data') ||
        beforeWorkflow.nodes.find((n) => n.type === 'python') ||
        beforeWorkflow.nodes.find((n) => (n.name || '').toLowerCase().includes('process'));

      expect(targetNode).toBeTruthy();
      const targetNodeName = (targetNode?.name || 'Process Data').trim();
      const desiredName = 'Process Data (Tripler)';

      const message = [
        `请严格只修改名为 "${targetNodeName}" 的节点，其他节点/边一律不要动。`,
        `1) 将该节点 name 改为 "${desiredName}"。`,
        `2) 将该节点 data.code 改为: result = {'output': input_data.get('value', 0) * 3}`,
        '3) 不要添加/删除节点或边。',
        '4) 输出简短确认即可。',
      ].join('\n');

      console.log(`[UX-WF-201] workflow_id=${workflow_id}`);
      console.log(`[UX-WF-201] Sending chat message:\n${message}`);

      const chatResp = await page.request.post(`${apiBaseUrl}/api/workflows/${workflow_id}/chat`, {
        data: { message },
      });
      diagnostics.chatStatus = chatResp.status();

      const chatBodyText = await chatResp.text();
      await attachText(testInfo, 'chat-response.txt', chatBodyText);

      const { json: chatJson, error: chatParseError } = parseJsonOrNull(chatBodyText);
      if (!chatResp.ok()) {
        diagnostics.chatParseError = chatParseError || null;
        diagnostics.chatErrorBodySnippet = chatBodyText.slice(0, 2000);
        throw new Error(`Chat request failed: HTTP ${chatResp.status()}`);
      }

      const chatData = chatJson as ChatResponse;
      await attachJson(testInfo, 'chat-response.json', {
        ai_message: chatData?.ai_message,
        intent: chatData?.intent,
        confidence: chatData?.confidence,
        modifications_count: chatData?.modifications_count,
        react_steps_count: Array.isArray(chatData?.react_steps) ? chatData.react_steps.length : 0,
      });

      const afterWorkflow = chatData.workflow;
      await attachJson(testInfo, 'workflow-after.json', summarizeWorkflow(afterWorkflow));

      const updatedNode =
        afterWorkflow.nodes.find((n) => n.id === targetNode?.id) ||
        afterWorkflow.nodes.find((n) => (n.name || '').includes('Tripler'));

      expect(updatedNode).toBeTruthy();
      expect(updatedNode?.name || '').toContain('Tripler');

      const code = String(updatedNode?.data?.code ?? '');
      expect(code).toMatch(/\*\s*3/);
    } catch (error) {
      await attachJson(testInfo, 'diagnostics.json', diagnostics);
      throw error;
    }
  });

  test('should reject isolated-node modification via chat using real LLM', async (
    { page, seedWorkflow },
    testInfo,
  ) => {
    test.skip(process.env.E2E_TEST_MODE !== 'fullreal', 'Requires E2E_TEST_MODE=fullreal');
    test.skip(!process.env.OPENAI_API_KEY, 'Requires OPENAI_API_KEY for real LLM testing');

    const apiBaseUrl = getApiBaseUrl();
    const diagnostics: Record<string, unknown> = {
      apiBaseUrl,
      workflowId: null,
      chatStatus: null,
      isolatedNodeId: null,
      isolatedNodeName: null,
    };

    try {
      const { workflow_id } = await seedWorkflow({
        fixtureType: 'with_isolated_nodes',
        projectId: 'e2e_fullreal_isolated_reject',
        customMetadata: { test_case: 'UX-WF-201', scenario: 'isolated_node_rejected' },
      });
      diagnostics.workflowId = workflow_id;

      await page.goto(`/workflows/${workflow_id}/edit?projectId=e2e_fullreal_isolated_reject`);
      await page.waitForSelector('[data-testid="workflow-canvas"]', {
        state: 'visible',
        timeout: 20000,
      });

      const beforeResp = await page.request.get(`${apiBaseUrl}/api/workflows/${workflow_id}`);
      expect(beforeResp.ok()).toBeTruthy();
      const beforeWorkflow = (await beforeResp.json()) as WorkflowResponse;
      await attachJson(testInfo, 'workflow-before.json', summarizeWorkflow(beforeWorkflow));

      const isolatedIds = computeIsolatedNodeIds(beforeWorkflow);
      expect(isolatedIds.size).toBeGreaterThan(0);

      const isolatedNode =
        beforeWorkflow.nodes.find((n) => isolatedIds.has(n.id) && (n.name || '').includes('Isolated')) ||
        beforeWorkflow.nodes.find((n) => isolatedIds.has(n.id));

      expect(isolatedNode).toBeTruthy();
      diagnostics.isolatedNodeId = isolatedNode?.id || null;
      diagnostics.isolatedNodeName = isolatedNode?.name || null;

      const isolatedNameForPrompt = (isolatedNode?.name || isolatedNode?.id || 'isolated node').trim();
      const beforeIsolatedCode = String(isolatedNode?.data?.code ?? '');

      const message = [
        `请修改名为 "${isolatedNameForPrompt}" 的节点：`,
        '把 data.code 改为: result = {"modified": true}',
        '注意：只修改这个孤立节点，不要修改主子图。',
      ].join('\n');

      console.log(`[UX-WF-201] workflow_id=${workflow_id}`);
      console.log(`[UX-WF-201] Requesting isolated-node modification:\n${message}`);

      const chatResp = await page.request.post(`${apiBaseUrl}/api/workflows/${workflow_id}/chat`, {
        data: { message },
      });
      diagnostics.chatStatus = chatResp.status();

      const chatBodyText = await chatResp.text();
      await attachText(testInfo, 'chat-response.txt', chatBodyText);

      const { json: chatJson, error: chatParseError } = parseJsonOrNull(chatBodyText);
      if (chatResp.status() === 400) {
        diagnostics.chatParseError = chatParseError || null;
        const detail = chatJson?.detail ?? chatJson;
        await attachJson(testInfo, 'chat-error.json', detail);
        expect(detail?.code).toBe('workflow_modification_rejected');
        return;
      }

      if (!chatResp.ok()) {
        diagnostics.chatParseError = chatParseError || null;
        diagnostics.chatErrorBodySnippet = chatBodyText.slice(0, 2000);
        throw new Error(`Chat request failed: HTTP ${chatResp.status()}`);
      }

      const chatData = chatJson as ChatResponse;
      await attachJson(testInfo, 'chat-response.json', {
        ai_message: chatData?.ai_message,
        intent: chatData?.intent,
        confidence: chatData?.confidence,
        modifications_count: chatData?.modifications_count,
      });

      // If the LLM safely refuses (HTTP 200), assert isolated node remains unchanged.
      const afterWorkflow = chatData.workflow;
      await attachJson(testInfo, 'workflow-after.json', summarizeWorkflow(afterWorkflow));

      const afterIsolated = afterWorkflow.nodes.find((n) => n.id === isolatedNode?.id);
      expect(afterIsolated).toBeTruthy();

      const afterIsolatedCode = String(afterIsolated?.data?.code ?? '');
      expect(afterIsolatedCode).toBe(beforeIsolatedCode);
    } catch (error) {
      await attachJson(testInfo, 'diagnostics.json', diagnostics);
      throw error;
    }
  });
});
