/**
 * Vitest 测试环境设置
 *
 * 这个文件会在所有测试运行之前执行
 */

import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';

// 扩展 Vitest 的 expect 断言，添加 @testing-library/jest-dom 的匹配器
expect.extend(matchers);

// 每个测试后自动清理 DOM
afterEach(() => {
  cleanup();
});

// Mock window.matchMedia（Ant Design 需要）
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock IntersectionObserver（某些组件可能需要）
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return [];
  }
  unobserve() {}
} as any;
