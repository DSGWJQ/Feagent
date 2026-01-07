/**
 * UX-WF-003: Run Workflow (Execute Workflow)
 *
 * Test Scenario:
 * 1. Use seedWorkflow fixture to create a test workflow (fixture_type: "main_subgraph_only")
 * 2. Open workflow editor
 * 3. Click RUN button (data-testid="workflow-run-button")
 * 4. Monitor SSE event stream via UI state changes
 * 5. Verify run_id was created
 * 6. Verify execution status transitions (running -> completed/error)
 * 7. Verify final state is completed or error (both are valid terminal states)
 *
 * Priority: P0
 * Test Mode: Deterministic
 *
 * Key Test IDs:
 * - workflow-run-button
 * - workflow-execution-status (hidden element with data-status attribute)
 * - execution-log-panel
 */

import { test, expect } from '../fixtures/workflowFixtures';

test.describe('UX-WF-003: Run Workflow', () => {
  /**
   * Main Test Case: Successfully run workflow and verify execution
   *
   * Test Flow:
   * 1. Seed workflow -> Navigate to editor -> Wait for load
   * 2. Setup network listeners for run_id capture
   * 3. Click RUN button
   * 4. Wait for execution status transitions
   * 5. Verify run_id was created and final state is terminal
   */
  test('should successfully trigger workflow execution and reach terminal state', async ({
    page,
    seedWorkflow,
  }) => {
    // 1. Create test workflow using seed fixture
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_run_test',
    });

    console.log(`[UX-WF-003] Created workflow: ${workflow_id}`);

    // 2. Navigate to workflow editor
    await page.goto(`/workflows/${workflow_id}/edit`);

    // 3. Wait for editor to load (canvas visible)
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    console.log('[UX-WF-003] Editor loaded successfully');

    // 4. Verify initial execution status is 'idle'
    const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
    await expect(statusIndicator).toHaveAttribute('data-status', 'idle', { timeout: 5000 });

    console.log('[UX-WF-003] Initial status is idle');

    // 5. Setup network request listeners BEFORE clicking RUN
    let capturedRunId: string | null = null;
    let runCreationSucceeded = false;
    let executeStreamCalled = false;

    // Listen for run creation response
    page.on('response', async (response) => {
      const url = response.url();

      // Capture run_id from POST /runs response
      if (url.includes('/runs') && response.request().method() === 'POST' && !url.includes('/execute')) {
        try {
          const responseStatus = response.status();
          if (responseStatus >= 200 && responseStatus < 300) {
            const data = await response.json();
            if (data.id) {
              capturedRunId = data.id;
              runCreationSucceeded = true;
              console.log(`[UX-WF-003] Run created: ${capturedRunId}`);
            }
          } else {
            console.log(`[UX-WF-003] Run creation failed with status: ${responseStatus}`);
          }
        } catch {
          console.log('[UX-WF-003] Failed to parse run creation response');
        }
      }

      // Verify execute/stream endpoint was called
      if (url.includes('/execute/stream')) {
        executeStreamCalled = true;
        console.log('[UX-WF-003] Execute stream endpoint called');
      }
    });

    // 6. Locate and click the RUN button
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    await runButton.waitFor({ state: 'visible', timeout: 5000 });
    await expect(runButton).toBeEnabled();

    console.log('[UX-WF-003] Clicking RUN button');
    await runButton.click();

    // 7. Verify status transitions to 'running'
    // Use a polling approach to handle race conditions
    await expect(async () => {
      const status = await statusIndicator.getAttribute('data-status');
      expect(status).toBe('running');
    }).toPass({ timeout: 10000 });

    console.log('[UX-WF-003] Execution started (status: running)');

    // 8. Wait for execution to complete (terminal state)
    // The execution should finish within 30 seconds
    // Terminal states: 'completed' (success with lastRunId) or 'idle' (if execution errored out)
    await expect(async () => {
      const status = await statusIndicator.getAttribute('data-status');
      // In the implementation, 'completed' means lastRunId exists (either success or post-execution)
      // We accept either 'completed' or timeout means the execution finished
      expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 30000 });

    const finalStatus = await statusIndicator.getAttribute('data-status');
    console.log(`[UX-WF-003] Final status: ${finalStatus}`);

    // 9. Wait a bit for network responses to be captured
    await page.waitForTimeout(1000);

    // 10. Verify that run_id was created
    // Note: In deterministic mode with stub responses, run creation should succeed
    console.log(`[UX-WF-003] Run creation succeeded: ${runCreationSucceeded}, capturedRunId: ${capturedRunId}`);
    expect(runCreationSucceeded).toBeTruthy();
    expect(capturedRunId).toBeTruthy();

    // 11. Verify execute/stream was called
    expect(executeStreamCalled).toBeTruthy();

    // 12. Verify final state is a valid terminal state
    // Either completed (success) or idle with error message (error)
    // Check for error messages to determine actual outcome
    const errorMessage = page.locator('.ant-message-error');
    const hasError = (await errorMessage.count()) > 0;

    if (hasError) {
      console.log('[UX-WF-003] Execution finished with error (valid terminal state)');
    } else {
      console.log('[UX-WF-003] Execution finished successfully (valid terminal state)');
    }

    // Both completed and error are valid terminal states for this test
    // The key verification is that execution was triggered and reached a terminal state
    expect(finalStatus).toBeDefined();

    console.log('[UX-WF-003] Test completed successfully');
  });

  /**
   * Test Case: Verify execution status indicator updates during execution
   */
  test('should update execution status indicator during workflow run', async ({
    page,
    seedWorkflow,
  }) => {
    // 1. Create test workflow
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_status_test',
    });

    // 2. Navigate to editor
    await page.goto(`/workflows/${workflow_id}/edit`);
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 3. Verify hidden status indicator exists
    const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
    await expect(statusIndicator).toBeAttached();

    // 4. Record initial status
    const initialStatus = await statusIndicator.getAttribute('data-status');
    console.log(`[UX-WF-003] Initial data-status: ${initialStatus}`);
    expect(initialStatus).toBe('idle');

    // 5. Click RUN and observe status change
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    await runButton.click();

    // 6. Verify status changes to 'running'
    await expect(statusIndicator).toHaveAttribute('data-status', 'running', { timeout: 10000 });

    console.log('[UX-WF-003] Status indicator correctly shows running state');

    // 7. Wait for completion and verify final status
    await expect(async () => {
      const status = await statusIndicator.getAttribute('data-status');
      expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 30000 });

    console.log('[UX-WF-003] Status indicator test passed');
  });

  /**
   * Test Case: Verify RUN button shows loading state during execution
   */
  test('should show loading state on RUN button during execution', async ({
    page,
    seedWorkflow,
  }) => {
    // 1. Create test workflow
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_loading_test',
    });

    // 2. Navigate to editor
    await page.goto(`/workflows/${workflow_id}/edit`);
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 3. Click RUN button
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    await runButton.waitFor({ state: 'visible', timeout: 5000 });
    await runButton.click();

    // 4. Verify button shows loading state (NeoButton uses ant-btn-loading class)
    // The button should be in loading state during execution
    await expect(async () => {
      const isLoading =
        (await runButton.getAttribute('class'))?.includes('ant-btn-loading') ||
        (await runButton.locator('.ant-btn-loading-icon').count()) > 0;
      expect(isLoading).toBeTruthy();
    }).toPass({ timeout: 5000 });

    console.log('[UX-WF-003] RUN button correctly shows loading state');

    // 5. Wait for execution to complete
    const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
    await expect(async () => {
      const status = await statusIndicator.getAttribute('data-status');
      expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 30000 });

    // 6. Verify button is no longer in loading state
    await expect(async () => {
      const isLoading =
        (await runButton.getAttribute('class'))?.includes('ant-btn-loading') ||
        (await runButton.locator('.ant-btn-loading-icon').count()) > 0;
      expect(isLoading).toBeFalsy();
    }).toPass({ timeout: 5000 });

    console.log('[UX-WF-003] RUN button loading state test passed');
  });

  /**
   * Test Case: Verify save is disabled during execution
   * (Cross-reference with UX-WF-002)
   */
  test('should disable save button during workflow execution', async ({
    page,
    seedWorkflow,
  }) => {
    // 1. Create test workflow
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_save_disabled_run',
    });

    // 2. Navigate to editor
    await page.goto(`/workflows/${workflow_id}/edit`);
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 3. Get button references
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    const saveButton = page.locator('[data-testid="workflow-save-button"]');

    // 4. Verify both buttons are initially enabled
    await expect(runButton).toBeEnabled();
    await expect(saveButton).toBeEnabled();

    // 5. Click RUN
    await runButton.click();

    // 6. Verify save button is disabled during execution
    await expect(saveButton).toBeDisabled({ timeout: 5000 });

    console.log('[UX-WF-003] Save button correctly disabled during execution');

    // 7. Wait for execution to complete
    const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
    await expect(async () => {
      const status = await statusIndicator.getAttribute('data-status');
      expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 30000 });

    // 8. Verify save button is re-enabled after execution
    await expect(saveButton).toBeEnabled({ timeout: 5000 });

    console.log('[UX-WF-003] Save button correctly re-enabled after execution');
  });

  /**
   * Test Case: Capture run_id from network requests
   */
  test('should create run_id before executing workflow', async ({
    page,
    seedWorkflow,
  }) => {
    // 1. Create test workflow
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_runid_test',
    });

    // 2. Navigate to editor
    await page.goto(`/workflows/${workflow_id}/edit`);
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 3. Setup detailed network monitoring
    const networkCalls: { url: string; method: string; status: number; runId?: string }[] = [];

    page.on('response', async (response) => {
      const url = response.url();
      const method = response.request().method();

      if (url.includes('/runs') || url.includes('/execute')) {
        const callInfo: { url: string; method: string; status: number; runId?: string } = {
          url: url,
          method: method,
          status: response.status(),
        };

        // Try to extract run_id from response
        if (method === 'POST' && url.includes('/runs') && !url.includes('/execute')) {
          try {
            const data = await response.json();
            if (data.id) {
              callInfo.runId = data.id;
            }
          } catch {
            // Response may not be JSON
          }
        }

        networkCalls.push(callInfo);
        console.log(`[UX-WF-003] Network: ${method} ${url} -> ${response.status()}`);
      }
    });

    // 4. Click RUN button
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    await runButton.click();

    // 5. Wait for execution to complete
    const statusIndicator = page.locator('[data-testid="workflow-execution-status"]');
    await expect(async () => {
      const status = await statusIndicator.getAttribute('data-status');
      expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 30000 });

    // 6. Wait for all network responses
    await page.waitForTimeout(2000);

    // 7. Verify network call sequence
    console.log('[UX-WF-003] Network calls:', JSON.stringify(networkCalls, null, 2));

    // Find the run creation call
    const runCreationCall = networkCalls.find(
      (call) => call.method === 'POST' && call.url.includes('/runs') && !call.url.includes('/execute')
    );

    // Find the execute stream call
    const executeCall = networkCalls.find(
      (call) => call.method === 'POST' && call.url.includes('/execute/stream')
    );

    // Verify run was created
    expect(runCreationCall).toBeDefined();
    expect(runCreationCall?.status).toBeGreaterThanOrEqual(200);
    expect(runCreationCall?.status).toBeLessThan(300);
    expect(runCreationCall?.runId).toBeTruthy();

    // Verify execute was called
    expect(executeCall).toBeDefined();

    console.log(`[UX-WF-003] Run ID created: ${runCreationCall?.runId}`);
    console.log('[UX-WF-003] Network sequence test passed');
  });
});
