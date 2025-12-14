/**
 * 设计系统 - 颜色Token
 *
 * 设计原则：
 * - 专业科技蓝主色调（区别于Ant Design默认蓝）
 * - 完整的色阶系统（50-900）
 * - 语义化命名
 * - 无渐变色
 */

export const colors = {
  // 主色 - 专业科技蓝
  primary: {
    50: '#e6f0ff',
    100: '#b3d4ff',
    200: '#80b8ff',
    300: '#4d9bff',
    400: '#1a7fff',   // 主色
    500: '#0066e6',
    600: '#0052b3',
    700: '#003d80',
    800: '#00294d',
    900: '#00141a',
  },

  // 中性色 - 灰度系统
  neutral: {
    50: '#fafafa',
    100: '#f5f5f5',
    200: '#e8e8e8',
    300: '#d1d1d1',
    400: '#9e9e9e',
    500: '#6b6b6b',
    600: '#4a4a4a',
    700: '#2e2e2e',
    800: '#1a1a1a',
    900: '#0a0a0a',
    white: '#ffffff',
    black: '#000000',
  },

  // 语义色 - 功能性颜色
  semantic: {
    success: {
      main: '#10b981',
      light: '#34d399',
      dark: '#059669',
      bg: '#d1fae5',
    },
    warning: {
      main: '#f59e0b',
      light: '#fbbf24',
      dark: '#d97706',
      bg: '#fef3c7',
    },
    error: {
      main: '#ef4444',
      light: '#f87171',
      dark: '#dc2626',
      bg: '#fee2e2',
    },
    info: {
      main: '#3b82f6',
      light: '#60a5fa',
      dark: '#2563eb',
      bg: '#dbeafe',
    },
  },

  // 辅助色 - 特定功能模块
  accent: {
    agent: '#8b5cf6',      // 紫色 - Agent相关
    workflow: '#06b6d4',   // 青色 - Workflow相关
    tool: '#f97316',       // 橙红 - Tool相关
    notification: '#eb2f96', // 粉红 - Notification节点
    audio: '#eb2f96',      // 粉红 - Audio节点
  },

  // 叠加层 - 遮罩和半透明效果
  overlay: {
    10: 'rgba(0, 0, 0, 0.1)',
    20: 'rgba(0, 0, 0, 0.2)',
    30: 'rgba(0, 0, 0, 0.3)',
    40: 'rgba(0, 0, 0, 0.4)',
    50: 'rgba(0, 0, 0, 0.5)',
    60: 'rgba(0, 0, 0, 0.6)',
    70: 'rgba(0, 0, 0, 0.7)',
    80: 'rgba(0, 0, 0, 0.8)',
    90: 'rgba(0, 0, 0, 0.9)',
  },
} as const;

export type Colors = typeof colors;
