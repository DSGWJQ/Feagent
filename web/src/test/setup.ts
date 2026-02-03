/**
 * Vitest 测试环境设置
 *
 * 这个文件会在所有测试运行之前执行
 */

import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

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
globalThis.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return [];
  }
  unobserve() {}
} as any;

// Mock Element.scrollIntoView（聊天组件需要）
Element.prototype.scrollIntoView = vi.fn();

// Mock ResizeObserver（React Flow 需要）
globalThis.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
} as any;

// JSDOM 不支持 pseudo-elements 的 getComputedStyle 调用；部分 UI 库会传入第二参数（例如 '::before'）
const __originalGetComputedStyle = window.getComputedStyle;
window.getComputedStyle = ((elt: Element, _pseudoElt?: string | null) =>
  __originalGetComputedStyle(elt)) as any;
