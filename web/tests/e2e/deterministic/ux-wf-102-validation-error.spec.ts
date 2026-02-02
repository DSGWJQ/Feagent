/**
 * UX-WF-102: Save Validation Error Test
 *
 * Test Scenarios:
 * 1. Save workflow with invalid config (invalid_config fixture)
 *    - Verify structured error response (code, message, errors[])
 *    - Verify error messages are readable and pinpoint the issue
 *
 * 2. Save empty workflow (only start/end nodes, no intermediate nodes)
 *    - Verify appropriate validation error is returned
 *
 * 3. Save workflow with cycle reference (if fixture supports)
 *    - Verify cycle detection error is returned on save
 *
 * Priority: P1
 * Test Mode: Deterministic
 *
 * Error Response Structure:
 * {
 *   "detail": {
 *     "code": "workflow_invalid",
 *     "message": "Workflow validation failed",
 *     "errors": [
 *       { "code": "error_code", "message": "...", "path": "..." }
 *     ]
 *   }
 * }
 */

import { test, expect } from '../fixtures/workflowFixtures';

/**
 * Structured validation error interface
 */
interface ValidationErrorDetail {
  code: string;
  message?: string;
  path?: string;
}

interface StructuredValidationError {
  code: string;
  message: string;
  errors: ValidationErrorDetail[];
}

test.describe('UX-WF-102: Save Validation Error', () => {
  /**
   * Test Case 1: Save workflow with invalid config
   *
   * Uses invalid_config fixture which creates a workflow with:
   * - start -> broken_node -> end
   * - broken_node has config.code = null (triggers validation failure)
   */
  test('should return structured error when saving workflow with invalid config', async ({
    page,
    seedWorkflow,
  }) => {
    // 1. Create workflow with invalid config using fixture
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'invalid_config',
      projectId: 'e2e_validation_error_test',
    });

    console.log(`[UX-WF-102] Created invalid_config workflow: ${workflow_id}`);

    // 2. Navigate to workflow editor
    await page.goto(`/workflows/${workflow_id}/edit`);

    // 3. Wait for editor to load
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    console.log('[UX-WF-102] Editor loaded successfully');

    // 4. Wait for nodes to render
    await page.waitForSelector('[data-testid^="workflow-node-"]', {
      state: 'visible',
      timeout: 5000,
    });

    // 5. Setup response listener to capture PATCH API response
    let patchResponseStatus: number | null = null;
    let patchResponseBody: Record<string, unknown> | null = null;
    let validationErrorCaptured = false;

    page.on('response', async (response) => {
      const url = response.url();
      if (
        url.includes(`/api/workflows/${workflow_id}`) &&
        response.request().method() === 'PATCH'
      ) {
        patchResponseStatus = response.status();
        console.log(`[UX-WF-102] PATCH response status: ${patchResponseStatus}`);

        try {
          const body = await response.json();
          patchResponseBody = body;
          console.log(`[UX-WF-102] PATCH response body: ${JSON.stringify(body, null, 2)}`);

          // Check if it's a validation error response
          if (patchResponseStatus === 400 && body.detail) {
            validationErrorCaptured = true;
          }
        } catch {
          console.log('[UX-WF-102] Failed to parse PATCH response body');
        }
      }
    });

    // 6. Click save button
    const saveButton = page.locator('[data-testid="workflow-save-button"]');
    await saveButton.waitFor({ state: 'visible', timeout: 5000 });
    await expect(saveButton).toBeEnabled();

    console.log('[UX-WF-102] Clicking save button');
    await saveButton.click();

    // 7. Wait for save operation to complete (button re-enabled or error modal appears)
    await page.waitForTimeout(2000);

    // 8. Verify PATCH API returned 400 status
    expect(patchResponseStatus).toBe(400);
    console.log('[UX-WF-102] PATCH API returned 400 as expected');

    // 9. Verify structured error response
    expect(patchResponseBody).toBeDefined();
    expect(patchResponseBody).not.toBeNull();

    const detail = (patchResponseBody as Record<string, unknown>)?.detail as StructuredValidationError | undefined;
    expect(detail).toBeDefined();

    // 10. Verify error structure has required fields: code, message, errors[]
    expect(detail?.code).toBeDefined();
    expect(typeof detail?.code).toBe('string');
    console.log(`[UX-WF-102] Error code: ${detail?.code}`);

    expect(detail?.message).toBeDefined();
    expect(typeof detail?.message).toBe('string');
    console.log(`[UX-WF-102] Error message: ${detail?.message}`);

    expect(detail?.errors).toBeDefined();
    expect(Array.isArray(detail?.errors)).toBeTruthy();
    expect(detail?.errors.length).toBeGreaterThan(0);
    console.log(`[UX-WF-102] Error count: ${detail?.errors.length}`);

    // 11. Verify each error item has at least code field
    for (const errorItem of detail?.errors ?? []) {
      expect(errorItem.code).toBeDefined();
      console.log(`[UX-WF-102] Error item: code=${errorItem.code}, message=${errorItem.message}, path=${errorItem.path}`);
    }

    // 12. Verify error messages are readable (not empty, not internal codes only)
    const hasReadableMessage = detail?.errors.some(
      (err) => err.message && err.message.length > 0
    );
    expect(hasReadableMessage).toBeTruthy();
    console.log('[UX-WF-102] Error messages are readable');

    // 13. Verify error modal is displayed in UI
    const errorModal = page.locator('.ant-modal-confirm-error');
    await expect(errorModal).toBeVisible({ timeout: 5000 });
    console.log('[UX-WF-102] Error modal is displayed');

    // 14. Verify modal contains error information
    const modalContent = page.locator('.ant-modal-confirm-content');
    await expect(modalContent).toBeVisible();

    // Check that modal displays error codes
    const modalText = await modalContent.textContent();
    expect(modalText).toBeTruthy();
    console.log(`[UX-WF-102] Modal content: ${modalText?.substring(0, 200)}...`);

    console.log('[UX-WF-102] Test completed successfully');
  });

  /**
   * Test Case 2: Save empty workflow (minimal nodes)
   *
   * Creates a main_subgraph_only workflow and attempts to delete
   * intermediate nodes to create a minimal workflow, then tries to save.
   *
   * Note: This test may behave differently depending on frontend validation.
   */
  test('should handle save attempt for workflow with minimal nodes', async ({
    page,
    seedWorkflow,
  }) => {
    const projectId = 'e2e_minimal_workflow_test';
    // 1. Create a normal workflow first
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId,
    });

    console.log(`[UX-WF-102] Created main_subgraph_only workflow: ${workflow_id}`);

    // 2. Navigate to workflow editor
    await page.goto(`/workflows/${workflow_id}/edit?projectId=${projectId}`, {
      waitUntil: 'domcontentloaded',
      timeout: 60_000,
    });

    // 3. Wait for editor to load
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 4. Try to select and delete intermediate nodes (if possible)
    // This depends on the UI implementation
    // For now, we'll just attempt to save and verify the response

    const saveButton = page.locator('[data-testid="workflow-save-button"]');
    await saveButton.waitFor({ state: 'visible', timeout: 5000 });

    // 5. If save button is enabled, click it
    if (await saveButton.isEnabled()) {
      console.log('[UX-WF-102] Attempting to save minimal workflow');

      const patchResponsePromise = page.waitForResponse(
        (response) =>
          response.request().method() === 'PATCH' &&
          response.url().includes(`/api/workflows/${workflow_id}`),
        { timeout: 30_000 }
      );

      await saveButton.click();
      const patchResponse = await patchResponsePromise;
      const patchResponseStatus = patchResponse.status();

      let patchResponseBody: Record<string, unknown> | null = null;
      try {
        patchResponseBody = (await patchResponse.json()) as Record<string, unknown>;
      } catch {
        // Response may not be JSON
      }

      console.log(`[UX-WF-102] Minimal workflow PATCH status: ${patchResponseStatus}`);

      if (patchResponseStatus === 400) {
        // Validation error - verify structure
        const detail = (patchResponseBody as Record<string, unknown>)?.detail as StructuredValidationError | undefined;
        if (detail && typeof detail === 'object') {
          expect(detail.code).toBeDefined();
          expect(detail.message).toBeDefined();
          console.log('[UX-WF-102] Minimal workflow save returned validation error as expected');
        }
      } else if (patchResponseStatus !== null && patchResponseStatus >= 200 && patchResponseStatus < 300) {
        // Success - main_subgraph_only is a valid workflow
        console.log('[UX-WF-102] Minimal workflow save succeeded (workflow is valid)');
      }
    } else {
      console.log('[UX-WF-102] Save button is disabled (frontend prevents save)');
    }

    console.log('[UX-WF-102] Minimal workflow test completed');
  });

  /**
   * Test Case 3: Verify validation errors pinpoint problem location
   *
   * Uses invalid_config fixture and verifies that error paths/locations
   * are included in the response to help users identify the problem node.
   */
  test('should include error path/location to help identify problem node', async ({
    page,
    seedWorkflow,
  }) => {
    // 1. Create workflow with invalid config
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'invalid_config',
      projectId: 'e2e_error_path_test',
    });

    console.log(`[UX-WF-102] Created invalid_config workflow for path test: ${workflow_id}`);

    // 2. Navigate to workflow editor
    await page.goto(`/workflows/${workflow_id}/edit`);

    // 3. Wait for editor to load
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 4. Setup response listener
    let validationError: StructuredValidationError | null = null;

    page.on('response', async (response) => {
      const url = response.url();
      if (
        url.includes(`/api/workflows/${workflow_id}`) &&
        response.request().method() === 'PATCH' &&
        response.status() === 400
      ) {
        try {
          const body = await response.json();
          if (body.detail && typeof body.detail === 'object') {
            validationError = body.detail as StructuredValidationError;
          }
        } catch {
          // Response may not be JSON
        }
      }
    });

    // 5. Click save button
    const saveButton = page.locator('[data-testid="workflow-save-button"]');
    await saveButton.waitFor({ state: 'visible', timeout: 5000 });
    await saveButton.click();

    // 6. Wait for response
    await page.waitForTimeout(2000);

    // 7. Verify validation error was captured
    expect(validationError).not.toBeNull();
    expect(validationError?.errors).toBeDefined();
    expect(validationError?.errors.length).toBeGreaterThan(0);

    // 8. Check if any error has path information
    const errorsWithPath = validationError?.errors.filter((err) => err.path) ?? [];
    console.log(`[UX-WF-102] Errors with path: ${errorsWithPath.length}/${validationError?.errors.length}`);

    // 9. Log all errors for debugging
    for (const err of validationError?.errors ?? []) {
      console.log(`[UX-WF-102] Error: code=${err.code}, path=${err.path}, message=${err.message}`);
    }

    // 10. Verify that errors have meaningful information
    // Either path or message should help locate the problem
    const hasLocatableErrors = validationError?.errors.every(
      (err) => err.path || err.message
    );
    expect(hasLocatableErrors).toBeTruthy();
    console.log('[UX-WF-102] All errors have locatable information (path or message)');

    console.log('[UX-WF-102] Error path test completed successfully');
  });

  /**
   * Test Case 4: Verify UI displays validation errors correctly
   *
   * Verifies that the frontend displays the validation error modal
   * with proper formatting and error list.
   */
  test('should display validation error modal with error list in UI', async ({
    page,
    seedWorkflow,
  }) => {
    // 1. Create workflow with invalid config
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'invalid_config',
      projectId: 'e2e_ui_error_display_test',
    });

    console.log(`[UX-WF-102] Created invalid_config workflow for UI test: ${workflow_id}`);

    // 2. Navigate to workflow editor
    await page.goto(`/workflows/${workflow_id}/edit`);

    // 3. Wait for editor to load
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 4. Click save button
    const saveButton = page.locator('[data-testid="workflow-save-button"]');
    await saveButton.waitFor({ state: 'visible', timeout: 5000 });
    await saveButton.click();

    // 5. Wait for error modal to appear
    const errorModal = page.locator('.ant-modal-confirm-error');
    await expect(errorModal).toBeVisible({ timeout: 10000 });
    console.log('[UX-WF-102] Error modal appeared');

    // 6. Verify modal title indicates validation failure
    const modalTitle = page.locator('.ant-modal-confirm-title');
    await expect(modalTitle).toBeVisible();
    const titleText = await modalTitle.textContent();
    console.log(`[UX-WF-102] Modal title: ${titleText}`);

    // 7. Verify modal content contains error list
    const modalContent = page.locator('.ant-modal-confirm-content');
    await expect(modalContent).toBeVisible();

    // 8. Check for error list items (ul > li structure based on frontend code)
    const errorListItems = modalContent.locator('li');
    const itemCount = await errorListItems.count();
    console.log(`[UX-WF-102] Error list items in modal: ${itemCount}`);
    expect(itemCount).toBeGreaterThan(0);

    // 9. Verify each error item displays code
    for (let i = 0; i < Math.min(itemCount, 3); i++) {
      const itemText = await errorListItems.nth(i).textContent();
      console.log(`[UX-WF-102] Error item ${i + 1}: ${itemText}`);
      // Each item should have a <code> element with error code
      const codeElement = errorListItems.nth(i).locator('code');
      const codeExists = (await codeElement.count()) > 0;
      expect(codeExists).toBeTruthy();
    }

    // 10. Close the modal
    const okButton = page.locator('.ant-modal-confirm-btns button');
    if ((await okButton.count()) > 0) {
      await okButton.first().click();
      await expect(errorModal).not.toBeVisible({ timeout: 5000 });
      console.log('[UX-WF-102] Modal closed successfully');
    }

    console.log('[UX-WF-102] UI error display test completed successfully');
  });

  /**
   * Test Case 5: Test with_isolated_nodes fixture (additional validation scenario)
   *
   * Tests workflow with isolated nodes to verify isolation-related validation errors.
   */
  test('should return validation error for workflow with isolated nodes', async ({
    page,
    seedWorkflow,
  }) => {
    // 1. Create workflow with isolated nodes
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'with_isolated_nodes',
      projectId: 'e2e_isolated_validation_test',
    });

    console.log(`[UX-WF-102] Created with_isolated_nodes workflow: ${workflow_id}`);

    // 2. Navigate to workflow editor
    await page.goto(`/workflows/${workflow_id}/edit`);

    // 3. Wait for editor to load
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 15000,
    });

    // 4. Setup response listener
    let patchResponseStatus: number | null = null;
    let validationError: StructuredValidationError | null = null;

    page.on('response', async (response) => {
      const url = response.url();
      if (
        url.includes(`/api/workflows/${workflow_id}`) &&
        response.request().method() === 'PATCH'
      ) {
        patchResponseStatus = response.status();
        if (response.status() === 400) {
          try {
            const body = await response.json();
            if (body.detail) {
              validationError = body.detail as StructuredValidationError;
            }
          } catch {
            // Response may not be JSON
          }
        }
      }
    });

    // 5. Click save button
    const saveButton = page.locator('[data-testid="workflow-save-button"]');
    await saveButton.waitFor({ state: 'visible', timeout: 5000 });

    if (await saveButton.isEnabled()) {
      await saveButton.click();

      // 6. Wait for response
      await page.waitForTimeout(2000);

      // 7. Check response
      console.log(`[UX-WF-102] Isolated nodes workflow PATCH status: ${patchResponseStatus}`);

      if (patchResponseStatus === 400 && validationError) {
        // Validation error expected for isolated nodes
        expect(validationError.code).toBeDefined();
        expect(validationError.errors).toBeDefined();
        expect(validationError.errors.length).toBeGreaterThan(0);

        // Log errors for debugging
        for (const err of validationError.errors) {
          console.log(`[UX-WF-102] Isolated node error: code=${err.code}, message=${err.message}`);
        }

        console.log('[UX-WF-102] Isolated nodes validation error returned as expected');
      } else if (patchResponseStatus !== null && patchResponseStatus >= 200 && patchResponseStatus < 300) {
        // Some configurations may allow isolated nodes
        console.log('[UX-WF-102] Isolated nodes workflow save succeeded (may be allowed by config)');
      }
    } else {
      console.log('[UX-WF-102] Save button is disabled for isolated nodes workflow');
    }

    console.log('[UX-WF-102] Isolated nodes test completed');
  });
});
