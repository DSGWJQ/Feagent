/**
 * UX-WF-002: 保存工作流
 *
 * 测试场景:
 * 1. 使用 seedWorkflow fixture 创建测试工作流
 * 2. 打开工作流编辑器
 * 3. 修改工作流(添加节点或修改配置)
 * 4. 点击保存按钮
 * 5. 验证保存成功提示
 * 6. 验证 PATCH API 返回 2xx 状态码
 *
 * 优先级: P0
 * 测试模式: Deterministic
 */

import { test, expect } from '../fixtures/workflowFixtures';

test.describe('UX-WF-002: 保存工作流', () => {
  test('应该成功保存工作流并显示成功提示', async ({ page, seedWorkflow }) => {
    // 1. 创建测试工作流
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_save_test',
    });

    console.log(`[UX-WF-002] Created workflow: ${workflow_id}`);

    // 2. 导航到工作流编辑器
    await page.goto(`/workflows/${workflow_id}/edit`);

    // 3. 等待编辑器加载完成
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 10000,
    });

    console.log('[UX-WF-002] Editor loaded successfully');

    // 4. 等待初始数据加载(通过检查是否有节点渲染)
    // main_subgraph_only fixture 至少包含 start 和 end 节点
    await page.waitForSelector('[data-testid^="workflow-node-"]', {
      state: 'visible',
      timeout: 5000,
    });

    // 5. 修改工作流 - 通过拖拽添加一个新节点
    // 从节点面板拖拽一个 HTTP Request 节点到画布
    const paletteItem = page.locator('[data-testid="node-palette-item-httpRequest"]');
    await paletteItem.waitFor({ state: 'visible', timeout: 5000 });

    // 模拟拖拽: 点击面板中的节点(触发 onClick 事件添加节点)
    await paletteItem.click();

    console.log('[UX-WF-002] Added HTTP Request node');

    // 6. 等待节点被添加到画布(节点数量增加)
    // 给 React 一些时间来更新 DOM
    await page.waitForTimeout(500);

    // 7. 设置请求拦截器来监听 PATCH API 调用
    let patchRequestStatus: number | null = null;
    let patchRequestCompleted = false;

    page.on('response', async (response) => {
      const url = response.url();
      if (url.includes(`/api/workflows/${workflow_id}`) && response.request().method() === 'PATCH') {
        patchRequestStatus = response.status();
        patchRequestCompleted = true;
        console.log(`[UX-WF-002] PATCH API response status: ${patchRequestStatus}`);
      }
    });

    // 8. 点击保存按钮
    const saveButton = page.locator('[data-testid="workflow-save-button"]');
    await saveButton.waitFor({ state: 'visible', timeout: 5000 });

    // 确保保存按钮未被禁用
    await expect(saveButton).toBeEnabled();

    console.log('[UX-WF-002] Clicking save button');
    await saveButton.click();

    // 9. 等待保存完成 - 通过监听按钮的 loading 状态变化
    // 保存按钮在请求期间会显示 loading 状态,完成后恢复正常
    await expect(saveButton).toBeEnabled({ timeout: 10000 });

    console.log('[UX-WF-002] Save button re-enabled, checking results');

    // 10. 验证 PATCH API 返回 2xx 状态码
    // 等待一小段时间确保响应已被捕获
    await page.waitForTimeout(1000);

    expect(patchRequestCompleted).toBeTruthy();
    expect(patchRequestStatus).toBeGreaterThanOrEqual(200);
    expect(patchRequestStatus).toBeLessThan(300);

    console.log('[UX-WF-002] PATCH API validation passed');

    // 11. 验证保存成功提示
    // 前端使用 message.success() 显示成功提示
    // Ant Design message 组件会在页面上显示 "保存成功" 文本
    const successMessage = page.locator('.ant-message-success:has-text("保存成功")');
    await expect(successMessage).toBeVisible({ timeout: 5000 });

    console.log('[UX-WF-002] Success message displayed');

    // 12. 验证工作流状态正常(画布仍然可交互)
    const canvas = page.locator('[data-testid="workflow-canvas"]');
    await expect(canvas).toBeVisible();

    console.log('[UX-WF-002] Test completed successfully');
  });

  test('保存按钮在执行期间应该被禁用', async ({ page, seedWorkflow }) => {
    // 1. 创建测试工作流
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_save_disabled_test',
    });

    // 2. 导航到工作流编辑器
    await page.goto(`/workflows/${workflow_id}/edit`);

    // 3. 等待编辑器加载完成
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 10000,
    });

    // 4. 等待运行按钮和保存按钮都可见
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    const saveButton = page.locator('[data-testid="workflow-save-button"]');

    await runButton.waitFor({ state: 'visible', timeout: 5000 });
    await saveButton.waitFor({ state: 'visible', timeout: 5000 });

    // 5. 点击运行按钮(触发执行)
    await runButton.click();

    // 6. 在执行期间,保存按钮应该被禁用
    // 验证保存按钮在执行期间被禁用（避免执行过快导致状态窗口过短）
    await expect(saveButton).toBeDisabled({ timeout: 5000 });

    console.log('[UX-WF-002] Save button is correctly disabled during execution');
  });

  test('保存空工作流应该失败并显示错误提示', async ({ page, seedWorkflow }) => {
    // 1. 创建测试工作流
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_save_empty_test',
    });

    // 2. 导航到工作流编辑器
    await page.goto(`/workflows/${workflow_id}/edit`);

    // 3. 等待编辑器加载完成
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 10000,
    });

    // 4. 拦截保存请求并将 payload 强制改为空（模拟“空工作流保存”）
    let emptySaveIntercepted = false;
    await page.route('**/*', async (route, request) => {
      if (request.method() !== 'PATCH' || !request.url().includes(`/workflows/${workflow_id}`)) {
        await route.continue();
        return;
      }

      emptySaveIntercepted = true;
      const response = await route.fetch({
        method: 'PATCH',
        headers: request.headers(),
        postData: JSON.stringify({ nodes: [], edges: [] }),
      });
      await route.fulfill({ response });
    });

    // 5. 监听 PATCH API 响应
    let patchRequestFailed = false;

    page.on('response', async (response) => {
      const url = response.url();
      if (url.includes(`/api/workflows/${workflow_id}`) && response.request().method() === 'PATCH') {
        if (response.status() >= 400) {
          patchRequestFailed = true;
          console.log(`[UX-WF-002] PATCH API failed with status: ${response.status()}`);
        }
      }
    });

    // 6. 尝试保存(当前实现可能不允许保存空工作流)
    const saveButton = page.locator('[data-testid="workflow-save-button"]');

    // 如果保存按钮可用,点击它
    if (await saveButton.isEnabled()) {
      await saveButton.click();

      // 7. 验证错误提示或失败响应
      // 等待错误消息或 API 失败响应
      await page.waitForTimeout(2000);

      // 验证至少有以下之一发生:
      // - 显示错误消息
      // - PATCH API 返回错误状态码
      const hasErrorMessage =
        (await page.locator('.ant-message-error').count()) > 0 ||
        (await page.locator('.ant-notification-error').count()) > 0;

      expect(hasErrorMessage || patchRequestFailed).toBeTruthy();
      expect(emptySaveIntercepted).toBeTruthy();

      console.log(
        '[UX-WF-002] Empty workflow save correctly failed with error indication',
      );
    } else {
      console.log('[UX-WF-002] Save button is disabled for empty workflow (expected behavior)');
    }
  });
});
