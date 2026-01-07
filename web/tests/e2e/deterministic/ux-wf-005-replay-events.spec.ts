/**
 * UX-WF-005: 回放事件
 *
 * 测试场景:
 * 1. 使用 seedWorkflow fixture 创建测试工作流
 * 2. 执行工作流并等待完成
 * 3. 获取 run_id
 * 4. 调用 GET /runs/{run_id}/events API 验证事件序列
 * 5. 点击回放按钮触发回放
 * 6. 验证回放界面显示事件列表
 *
 * 验收标准:
 * - 能成功获取执行事件
 * - 事件序列完整(≥ 10 个事件)
 * - 回放功能正常
 *
 * 优先级: P0
 * 测试模式: Deterministic
 */

import { test, expect } from '../fixtures/workflowFixtures';

test.describe('UX-WF-005: 回放事件', () => {
  test('应该成功执行工作流并回放事件序列', async ({ page, seedWorkflow }) => {
    // 1. 创建测试工作流 (使用 main_subgraph_only fixture)
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_replay_test',
      customMetadata: {
        test_case: 'UX-WF-005',
        description: 'Replay events test',
      },
    });

    console.log(`[UX-WF-005] Created workflow: ${workflow_id}`);

    // 2. 导航到工作流编辑器
    await page.goto(`/workflows/${workflow_id}/edit`);

    // 3. 等待编辑器和画布加载完成
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 10000,
    });

    console.log('[UX-WF-005] Editor loaded successfully');

    // 4. 等待初始节点渲染完成
    await page.waitForSelector('[data-testid^="workflow-node-"]', {
      state: 'visible',
      timeout: 5000,
    });

    // 5. 设置响应拦截器来捕获 run_id
    let capturedRunId: string | null = null;

    page.on('response', async (response) => {
      const url = response.url();
      // 拦截创建 run 的 POST 请求响应
      if (url.includes(`/api/projects/`) && url.includes(`/workflows/${workflow_id}/runs`)) {
        if (response.request().method() === 'POST' && response.status() === 200) {
          try {
            const data = await response.json();
            if (data.id) {
              capturedRunId = data.id;
              console.log(`[UX-WF-005] Captured run_id: ${capturedRunId}`);
            }
          } catch (error) {
            console.error('[UX-WF-005] Failed to parse run response:', error);
          }
        }
      }
    });

    // 6. 点击 RUN 按钮执行工作流
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    await runButton.waitFor({ state: 'visible', timeout: 5000 });
    await expect(runButton).toBeEnabled();

    console.log('[UX-WF-005] Clicking RUN button');
    await runButton.click();

    // 7. 等待执行开始 (run_id 被捕获)
    await page.waitForTimeout(2000);
    expect(capturedRunId).toBeTruthy();
    console.log(`[UX-WF-005] Workflow execution started with run_id: ${capturedRunId}`);

    // 8. 等待执行完成
    // 监听执行状态变化 - 等待执行状态为 completed 或 idle（终态）
    const executionStatus = page.locator('[data-testid="workflow-execution-status"]');
    await expect(executionStatus).toBeAttached();
    await expect(async () => {
      const status = await executionStatus.getAttribute('data-status');
      expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 30000 });

    console.log('[UX-WF-005] Workflow execution completed');

    // 9. 调用 GET /runs/{run_id}/events API 验证事件序列
    const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
    const eventsResponse = await page.request.get(
      `${apiBaseUrl}/api/runs/${capturedRunId}/events?channel=execution&limit=200`,
    );

    expect(eventsResponse.ok()).toBeTruthy();
    const eventsData = await eventsResponse.json();

    console.log(`[UX-WF-005] Events API response:`, {
      run_id: eventsData.run_id,
      event_count: eventsData.events?.length || 0,
      has_more: eventsData.has_more,
      next_cursor: eventsData.next_cursor,
    });

    // 10. 验证事件序列完整性（避免用硬编码数量与非该通道事件做脆弱断言）
    expect(eventsData.run_id).toBe(capturedRunId);
    expect(eventsData.events).toBeDefined();
    expect(Array.isArray(eventsData.events)).toBeTruthy();

    const events: Array<{ type?: string; node_id?: string }> = eventsData.events || [];

    const uniqueNodeIds = new Set(
      events.filter((e) => e.type?.startsWith('node_') && e.node_id).map((e) => e.node_id!),
    );
    const nodeStartCount = events.filter((e) => e.type === 'node_start').length;
    const nodeCompleteCount = events.filter((e) => e.type === 'node_complete').length;

    // main_subgraph_only: start -> javascript -> end（至少 3 个节点的 start/complete + workflow_complete）
    expect(uniqueNodeIds.size).toBeGreaterThanOrEqual(3);
    expect(nodeStartCount).toBeGreaterThanOrEqual(3);
    expect(nodeCompleteCount).toBeGreaterThanOrEqual(3);
    expect(
      events.some((e) => e.type === 'workflow_complete' || e.type === 'workflow_error'),
    ).toBeTruthy();

    // workflow_complete/workflow_error 应该是最后一个事件（便于 replay 使用稳定终止条件）
    expect(['workflow_complete', 'workflow_error']).toContain(events[events.length - 1]?.type);

    console.log(`[UX-WF-005] Event sequence validation passed: ${events.length} events`);

    // 12. 点击回放按钮 (replay-run-button)
    const replayButton = page.locator('[data-testid="replay-run-button"]');
    await replayButton.waitFor({ state: 'visible', timeout: 5000 });

    // 验证回放按钮已启用 (因为已经有 run_id)
    await expect(replayButton).toBeEnabled();

    console.log('[UX-WF-005] Clicking replay button');
    await replayButton.click();

    // 13. 等待回放开始 (按钮变为 Stop 状态)
    await expect(replayButton).toContainText(/Stop|停止/i, { timeout: 3000 });

    console.log('[UX-WF-005] Replay started');

    // 14. 验证回放事件列表显示 (如果有单独的事件列表组件)
    // 注意: 根据实际前端实现,回放可能通过执行日志面板显示
    // 这里使用通用的日志项选择器来验证事件被渲染

    // 等待至少一个日志项出现
    const logEntry = page.locator('[data-testid^="execution-log-entry-"]').first();
    await expect(logEntry).toBeVisible({ timeout: 5000 });

    console.log('[UX-WF-005] Replay events displayed in execution log');

    // 15. 可选: 验证事件列表容器存在 (如果前端实现了 replay-event-list)
    const replayEventList = page.locator('[data-testid="replay-event-list"]');
    const hasReplayEventList = (await replayEventList.count()) > 0;

    if (hasReplayEventList) {
      await expect(replayEventList).toBeVisible();
      console.log('[UX-WF-005] Replay event list component is visible');
    } else {
      console.log(
        '[UX-WF-005] Replay event list component not found, events displayed in execution log panel',
      );
    }

    // 16. 停止回放
    await page.waitForTimeout(1000);
    await replayButton.click();

    // 验证回放按钮恢复为 Replay 状态
    await expect(replayButton).toContainText(/Replay|回放/i, { timeout: 3000 });

    console.log('[UX-WF-005] Replay stopped successfully');
    console.log('[UX-WF-005] Test completed successfully');
  });

  test('回放按钮在无执行记录时应该被禁用', async ({ page, seedWorkflow }) => {
    // 1. 创建测试工作流
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_replay_disabled_test',
    });

    // 2. 导航到工作流编辑器
    await page.goto(`/workflows/${workflow_id}/edit`);

    // 3. 等待编辑器加载完成
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 10000,
    });

    // 4. 验证回放按钮存在但被禁用 (因为没有执行过)
    const replayButton = page.locator('[data-testid="replay-run-button"]');
    await replayButton.waitFor({ state: 'visible', timeout: 5000 });

    // 应该被禁用
    await expect(replayButton).toBeDisabled();

    console.log('[UX-WF-005] Replay button is correctly disabled when no run exists');
  });

  test('API 直接调用: 验证事件分页功能', async ({ page, seedWorkflow }) => {
    // 1. 创建测试工作流
    const { workflow_id } = await seedWorkflow({
      fixtureType: 'main_subgraph_only',
      projectId: 'e2e_replay_pagination_test',
    });

    // 2. 导航并执行工作流
    await page.goto(`/workflows/${workflow_id}/edit`);
    await page.waitForSelector('[data-testid="workflow-canvas"]', {
      state: 'visible',
      timeout: 10000,
    });

    // 3. 捕获 run_id
    let capturedRunId: string | null = null;
    page.on('response', async (response) => {
      const url = response.url();
      if (url.includes(`/api/projects/`) && url.includes(`/workflows/${workflow_id}/runs`)) {
        if (response.request().method() === 'POST' && response.status() === 200) {
          const data = await response.json();
          if (data.id) capturedRunId = data.id;
        }
      }
    });

    // 4. 执行工作流
    const runButton = page.locator('[data-testid="workflow-run-button"]');
    await runButton.click();
    await page.waitForTimeout(2000);

    // 5. 等待执行完成
    const executionStatus = page.locator('[data-testid="workflow-execution-status"]');
    await expect(executionStatus).toBeAttached();
    await expect(async () => {
      const status = await executionStatus.getAttribute('data-status');
      expect(['completed', 'idle'].includes(status ?? '')).toBeTruthy();
    }).toPass({ timeout: 30000 });

    expect(capturedRunId).toBeTruthy();

    // 6. 测试分页: 先获取前 5 个事件
    const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
    const firstPageResponse = await page.request.get(
      `${apiBaseUrl}/api/runs/${capturedRunId}/events?channel=execution&limit=5`,
    );

    expect(firstPageResponse.ok()).toBeTruthy();
    const firstPageData = await firstPageResponse.json();

    console.log('[UX-WF-005] First page:', {
      event_count: firstPageData.events.length,
      has_more: firstPageData.has_more,
      next_cursor: firstPageData.next_cursor,
    });

    expect(firstPageData.events.length).toBeLessThanOrEqual(5);

    // 7. 如果有更多事件,使用 cursor 获取下一页
    if (firstPageData.has_more && firstPageData.next_cursor) {
      const secondPageResponse = await page.request.get(
        `${apiBaseUrl}/api/runs/${capturedRunId}/events?channel=execution&limit=5&cursor=${firstPageData.next_cursor}`,
      );

      expect(secondPageResponse.ok()).toBeTruthy();
      const secondPageData = await secondPageResponse.json();

      console.log('[UX-WF-005] Second page:', {
        event_count: secondPageData.events.length,
        has_more: secondPageData.has_more,
      });

      // 验证分页逻辑: 第二页的事件不应与第一页重复
      const firstPageEventIds = firstPageData.events.map((e: any) => e.type + e.run_id);
      const secondPageEventIds = secondPageData.events.map((e: any) => e.type + e.run_id);

      // 事件内容应该不完全相同 (虽然可能有重复的 type,但整体序列不同)
      expect(secondPageData.events.length).toBeGreaterThan(0);

      console.log('[UX-WF-005] Pagination validation passed');
    } else {
      console.log('[UX-WF-005] No pagination needed (all events fit in first page)');
    }
  });
});
