/**
 * 主题定义 - Dark/Light主题配置
 *
 * 定义不同主题下的CSS Variable值
 * Light主题通过反转neutral颜色实现
 * 支持新古典主义设计系统
 */

import { neoclassicalColors } from './tokens/neoclassicalColors';

export type ThemeMode = 'dark' | 'light';

export interface ThemeVariables {
  // Neutral colors (主要变化的颜色)
  '--color-neutral-50': string;
  '--color-neutral-100': string;
  '--color-neutral-200': string;
  '--color-neutral-300': string;
  '--color-neutral-400': string;
  '--color-neutral-500': string;
  '--color-neutral-600': string;
  '--color-neutral-700': string;
  '--color-neutral-800': string;
  '--color-neutral-900': string;

  // Primary colors (Gold)
  '--color-primary-50': string;
  '--color-primary-100': string;
  '--color-primary-200': string;
  '--color-primary-300': string;
  '--color-primary-400': string;
  '--color-primary-500': string;
  '--color-primary-600': string;
  '--color-primary-700': string;
  '--color-primary-800': string;
  '--color-primary-900': string;

  // Semantic
  '--color-success': string;
  '--color-warning': string;
  '--color-error': string;
  '--color-info': string;

  // Background & Border (基于neutral的语义化颜色)
  '--color-bg-primary': string;
  '--color-bg-secondary': string;
  '--color-bg-tertiary': string;
  '--color-border-primary': string;
  '--color-border-secondary': string;
  '--color-text-primary': string;
  '--color-text-secondary': string;
  '--color-text-tertiary': string;

  // Neoclassical (新古典主义变量)
  '--neo-bg': string;
  '--neo-surface': string;
  '--neo-surface-2': string;
  '--neo-text': string;
  '--neo-text-2': string;
  '--neo-border': string;
  '--neo-gold': string;
  '--neo-blue': string;
  '--neo-red': string;
  '--neo-focus': string;
}

/**
 * Dark主题配置（默认）
 */
export const darkTheme: ThemeVariables = {
  // Neutral scale (Dark Mode: Graphite/Stone)
  '--color-neutral-50': '#111827',     // neutral-900 (Background)
  '--color-neutral-100': '#1F2937',    // neutral-800 (Surface)
  '--color-neutral-200': '#374151',    // neutral-700 (Border)
  '--color-neutral-300': '#4B5563',    // neutral-600
  '--color-neutral-400': '#6B7280',    // neutral-500
  '--color-neutral-500': '#9CA3AF',    // neutral-400
  '--color-neutral-600': '#D1D5DB',    // neutral-300
  '--color-neutral-700': '#E5E7EB',    // neutral-200
  '--color-neutral-800': '#F3F4F6',    // neutral-100
  '--color-neutral-900': '#F9FAFB',    // neutral-50 (Text)

  // Primary (Gold)
  '--color-primary-50': '#78350F',
  '--color-primary-100': '#92400E',
  '--color-primary-200': '#B45309',
  '--color-primary-300': '#D97706',
  '--color-primary-400': '#F59E0B',
  '--color-primary-500': '#FBBF24',
  '--color-primary-600': '#FCD34D',
  '--color-primary-700': '#FDE68A',
  '--color-primary-800': '#FEF3C7',
  '--color-primary-900': '#FFFBEB',

  // Semantic
  '--color-success': '#22C55E',
  '--color-warning': '#F59E0B',
  '--color-error': '#EF4444',
  '--color-info': '#60A5FA',

  // Semantic Backgrounds
  '--color-bg-primary': '#111827',
  '--color-bg-secondary': '#1F2937',
  '--color-bg-tertiary': '#374151',
  '--color-border-primary': '#374151',
  '--color-border-secondary': '#4B5563',
  '--color-text-primary': '#F9FAFB',
  '--color-text-secondary': '#D1D5DB',
  '--color-text-tertiary': '#9CA3AF',

  // Neoclassical - Dark theme
  '--neo-bg': neoclassicalColors.themeVars.dark['--neo-bg'],
  '--neo-surface': neoclassicalColors.themeVars.dark['--neo-surface'],
  '--neo-surface-2': neoclassicalColors.themeVars.dark['--neo-surface-2'],
  '--neo-text': neoclassicalColors.themeVars.dark['--neo-text'],
  '--neo-text-2': neoclassicalColors.themeVars.dark['--neo-text-2'],
  '--neo-border': neoclassicalColors.themeVars.dark['--neo-border'],
  '--neo-gold': neoclassicalColors.themeVars.dark['--neo-gold'],
  '--neo-blue': neoclassicalColors.themeVars.dark['--neo-blue'],
  '--neo-red': neoclassicalColors.themeVars.dark['--neo-red'],
  '--neo-focus': neoclassicalColors.themeVars.dark['--neo-focus'],
};

/**
 * Light主题配置（反转neutral颜色）
 */
export const lightTheme: ThemeVariables = {
  // Neutral scale (Light Mode: White/Stone)
  '--color-neutral-50': '#F9FAFB',
  '--color-neutral-100': '#F3F4F6',
  '--color-neutral-200': '#E5E7EB',
  '--color-neutral-300': '#D1D5DB',
  '--color-neutral-400': '#9CA3AF',
  '--color-neutral-500': '#6B7280',
  '--color-neutral-600': '#4B5563',
  '--color-neutral-700': '#374151',
  '--color-neutral-800': '#1F2937',
  '--color-neutral-900': '#111827',

  // Primary (Gold)
  '--color-primary-50': '#FFFBEB',
  '--color-primary-100': '#FEF3C7',
  '--color-primary-200': '#FDE68A',
  '--color-primary-300': '#FCD34D',
  '--color-primary-400': '#FBBF24',
  '--color-primary-500': '#F59E0B',
  '--color-primary-600': '#D97706',
  '--color-primary-700': '#B45309',
  '--color-primary-800': '#92400E',
  '--color-primary-900': '#78350F',

  // Semantic
  '--color-success': '#15803D',
  '--color-warning': '#D97706',
  '--color-error': '#DC2626',
  '--color-info': '#1E40AF',

  // Semantic Backgrounds
  '--color-bg-primary': '#FFFFFF',     // white
  '--color-bg-secondary': '#F9FAFB',   // neutral-50
  '--color-bg-tertiary': '#F3F4F6',    // neutral-100
  '--color-border-primary': '#E5E7EB', // neutral-200
  '--color-border-secondary': '#D1D5DB', // neutral-300
  '--color-text-primary': '#111827',   // neutral-900
  '--color-text-secondary': '#4B5563', // neutral-600
  '--color-text-tertiary': '#6B7280',  // neutral-500

  // Neoclassical - Light theme
  '--neo-bg': neoclassicalColors.themeVars.light['--neo-bg'],
  '--neo-surface': neoclassicalColors.themeVars.light['--neo-surface'],
  '--neo-surface-2': neoclassicalColors.themeVars.light['--neo-surface-2'],
  '--neo-text': neoclassicalColors.themeVars.light['--neo-text'],
  '--neo-text-2': neoclassicalColors.themeVars.light['--neo-text-2'],
  '--neo-border': neoclassicalColors.themeVars.light['--neo-border'],
  '--neo-gold': neoclassicalColors.themeVars.light['--neo-gold'],
  '--neo-blue': neoclassicalColors.themeVars.light['--neo-blue'],
  '--neo-red': neoclassicalColors.themeVars.light['--neo-red'],
  '--neo-focus': neoclassicalColors.themeVars.light['--neo-focus'],
};

/**
 * 获取主题配置
 */
export function getThemeVariables(mode: ThemeMode): ThemeVariables {
  return mode === 'dark' ? darkTheme : lightTheme;
}

/**
 * 应用主题到DOM
 */
export function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement;
  const variables = getThemeVariables(mode);

  // 添加过渡class
  root.classList.add('theme-transition');

  // 应用CSS Variables
  Object.entries(variables).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });

  // 设置data-theme属性（用于CSS选择器）
  root.setAttribute('data-theme', mode);

  // 300ms后移除过渡class（避免影响其他动画）
  setTimeout(() => {
    root.classList.remove('theme-transition');
  }, 300);
}

/**
 * 从localStorage读取主题偏好
 */
export function getStoredTheme(): ThemeMode {
  const stored = localStorage.getItem('theme-preference');
  if (stored === 'light' || stored === 'dark') {
    return stored;
  }
  return 'dark'; // 默认dark主题
}

/**
 * 保存主题偏好到localStorage
 */
export function storeTheme(mode: ThemeMode): void {
  localStorage.setItem('theme-preference', mode);
}
