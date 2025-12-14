/**
 * 设计系统 - 圆角BorderRadius Token
 *
 * 设计原则：
 * - 适度的圆角（企业风格）
 * - 渐进式圆角层级
 */

export const borderRadius = {
  none: '0',
  sm: '4px',
  base: '6px',
  md: '8px',
  lg: '12px',
  xl: '16px',
  full: '9999px',
} as const;

export type BorderRadius = typeof borderRadius;
