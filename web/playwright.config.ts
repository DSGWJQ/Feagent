import { defineConfig, devices } from '@playwright/test';
import { fileURLToPath } from 'node:url';

/**
 * Playwright E2E 测试配置
 * 支持三种测试模式:
 * - deterministic: 完全确定性 (Stub LLM + Mock HTTP)
 * - hybrid: 混合模式 (Replay LLM + WireMock HTTP)
 * - fullreal: 真实模式 (Real LLM + Real HTTP)
 */
export default defineConfig({
  // 测试目录根路径
  testDir: './tests/e2e',

  // 全局 setup/teardown
  globalSetup: fileURLToPath(new URL('./tests/e2e/global-setup.ts', import.meta.url)),
  globalTeardown: fileURLToPath(new URL('./tests/e2e/global-teardown.ts', import.meta.url)),

  // 全局配置
  timeout: 30000, // 默认超时 30 秒
  expect: {
    timeout: 5000, // 断言超时 5 秒
  },

  // 失败重试
  retries: process.env.CI ? 2 : 0,

  // 并行执行配置
  // Deterministic mode aims for stability over speed; use a single worker to avoid data races
  // (e.g. shared localStorage, global run persistence, backend state).
  workers: 1,
  fullyParallel: false, // 串行执行以避免数据竞争

  // 报告配置
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'test-results.json' }],
    ['list'],
  ],

  // 全局 baseURL
  use: {
    // Default to IPv4 loopback to avoid `localhost` resolving to `::1` on Windows
    // when dev server binds to 127.0.0.1 only.
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
    trace: 'on-first-retry', // 失败时记录 trace
    screenshot: 'only-on-failure', // 失败时截图
    video: 'retain-on-failure', // 失败时保留视频
    actionTimeout: 10000, // 操作超时 10 秒
  },

  // 测试项目配置
  projects: [
    {
      name: 'deterministic',
      testDir: './tests/e2e/deterministic',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
      },
      // Deterministic mode still includes backend seed + UI navigation (and sometimes side-effect confirms);
      // keep a generous per-test ceiling to avoid flaky timeouts on slower Windows/SQLite.
      timeout: 120000,
      retries: 1,
    },
    {
      name: 'hybrid',
      testDir: './tests/e2e/hybrid',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
      },
      timeout: 60000, // Replay 模式可能较慢
      retries: 1,
    },
    {
      name: 'fullreal',
      testDir: './tests/e2e/fullreal',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
      },
      timeout: 120000, // 真实 LLM 调用较慢
      retries: 0, // 真实模式不重试(避免多次调用 API)
    },
  ],

  // Web Server 配置 (可选)
  // If PLAYWRIGHT_BASE_URL is not provided, start (or reuse) a Vite dev server automatically.
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: 'npm run dev -- --host 127.0.0.1 --port 5173',
        url: 'http://127.0.0.1:5173',
        reuseExistingServer: !process.env.CI,
        timeout: 120000,
      },
});
