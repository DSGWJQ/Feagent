/**
 * UX-WF-001: Open Workflow Editor Test
 *
 * Test Scenarios:
 * 1. Create workflow via Seed API and open editor
 * 2. Verify canvas loads correctly
 * 3. Verify start and end nodes are visible
 *
 * Priority: P0
 * Test Mode: Deterministic
 */

import { test, expect } from '../fixtures/workflowFixtures';
import type { Page } from '@playwright/test';

async function gotoWorkflowEditor(page: Page, workflowId: string): Promise<void> {
  await page.goto(`/workflows/${workflowId}/edit`, {
    waitUntil: 'domcontentloaded',
    timeout: 60_000,
  });
}

test.describe('UX-WF-001: Open Workflow Editor', () => {
  /**
   * Test Case 1: Open editor and verify canvas loads
   *
   * Steps:
   * 1. Create workflow using seed API
   * 2. Navigate to /workflows/{id}/edit
   * 3. Verify canvas container is visible
   */
  test('should load workflow editor canvas successfully', async ({ page, seedWorkflow }) => {
    console.log('[UX-WF-001] Starting open editor test');

    // 1. Create workflow using seed API
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_open_editor_test',
    });

    console.log(`[UX-WF-001] Created workflow: ${workflow_id}`);

    // 2. Navigate to workflow editor
    await gotoWorkflowEditor(page, workflow_id);
    console.log('[UX-WF-001] Navigated to editor');

    // 3. Wait for canvas to load
    const canvas = page.locator('[data-testid="workflow-canvas"]');
    await expect(canvas).toBeVisible({ timeout: 15000 });
    console.log('[UX-WF-001] Canvas is visible');

    // 4. Verify canvas dimensions (should have non-zero size)
    const boundingBox = await canvas.boundingBox();
    expect(boundingBox).not.toBeNull();
    expect(boundingBox!.width).toBeGreaterThan(0);
    expect(boundingBox!.height).toBeGreaterThan(0);
    console.log(`[UX-WF-001] Canvas dimensions: ${boundingBox!.width}x${boundingBox!.height}`);

    console.log('[UX-WF-001] Test completed successfully');
  });

  /**
   * Test Case 2: Verify start node is visible
   *
   * Steps:
   * 1. Create workflow and open editor
   * 2. Verify start node has correct testid
   */
  test('should display start node on canvas', async ({ page, seedWorkflow }) => {
    console.log('[UX-WF-001] Starting start node visibility test');

    // 1. Create workflow
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_start_node_test',
    });

    // 2. Navigate to editor
    await gotoWorkflowEditor(page, workflow_id);

    // 3. Wait for canvas
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 4. Verify start node is visible
    const startNode = page.locator('[data-testid="workflow-node-start"]');
    await expect(startNode).toBeVisible({ timeout: 10000 });
    console.log('[UX-WF-001] Start node is visible');

    // 5. Verify start node has content
    const nodeContent = await startNode.textContent();
    expect(nodeContent).toBeTruthy();
    console.log(`[UX-WF-001] Start node content: ${nodeContent?.substring(0, 50)}`);

    console.log('[UX-WF-001] Start node test completed');
  });

  /**
   * Test Case 3: Verify end node is visible
   *
   * Steps:
   * 1. Create workflow and open editor
   * 2. Verify end node has correct testid
   */
  test('should display end node on canvas', async ({ page, seedWorkflow }) => {
    console.log('[UX-WF-001] Starting end node visibility test');

    // 1. Create workflow
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_end_node_test',
    });

    // 2. Navigate to editor
    await gotoWorkflowEditor(page, workflow_id);

    // 3. Wait for canvas
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 4. Verify end node is visible
    const endNode = page.locator('[data-testid="workflow-node-end"]');
    await expect(endNode).toBeVisible({ timeout: 10000 });
    console.log('[UX-WF-001] End node is visible');

    console.log('[UX-WF-001] End node test completed');
  });

  /**
   * Test Case 4: Verify RUN and SAVE buttons exist
   *
   * Steps:
   * 1. Create workflow and open editor
   * 2. Verify RUN and SAVE buttons have correct testids
   */
  test('should display RUN and SAVE buttons', async ({ page, seedWorkflow }) => {
    console.log('[UX-WF-001] Starting button visibility test');

    // 1. Create workflow
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_button_test',
    });

    // 2. Navigate to editor
    await gotoWorkflowEditor(page, workflow_id);

    // 3. Wait for canvas
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 4. Verify RUN button
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    await expect(runButton).toBeVisible({ timeout: 5000 });
    console.log('[UX-WF-001] RUN button is visible');

    // 5. Verify SAVE button
    const saveButton = page.locator('[data-testid="workflow-save-button"]');
    await expect(saveButton).toBeVisible({ timeout: 5000 });
    console.log('[UX-WF-001] SAVE button is visible');

    console.log('[UX-WF-001] Button test completed');
  });

  /**
   * Test Case 5: Verify consecutive editor opens (stability check)
   *
   * Opens the same editor multiple times to ensure no memory leaks or state issues
   */
  test('should handle consecutive editor opens', async ({ page, seedWorkflow }) => {
    console.log('[UX-WF-001] Starting stability test');

    // 1. Create workflow
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_stability_test',
    });

    // 2. Open editor 3 times
    for (let i = 1; i <= 3; i++) {
      console.log(`[UX-WF-001] Opening editor iteration ${i}`);

      await gotoWorkflowEditor(page, workflow_id);

      // Verify canvas loads each time
      const canvas = page.locator('[data-testid="workflow-canvas"]');
      await expect(canvas).toBeVisible({ timeout: 15000 });

      // Verify start node
      const startNode = page.locator('[data-testid="workflow-node-start"]');
      await expect(startNode).toBeVisible({ timeout: 10000 });

      console.log(`[UX-WF-001] Iteration ${i} passed`);

      // Navigate away
      if (i < 3) {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 60_000 });
        await page.waitForTimeout(500);
      }
    }

    console.log('[UX-WF-001] Stability test completed');
  });
});
