/**
 * 设计系统 - 设计Token统一导出
 *
 * 使用方式：
 * import { colors, typography, spacing, shadows, borderRadius } from '@/shared/styles/tokens';
 *
 * 示例：
 * const buttonStyle = {
 *   backgroundColor: colors.primary[400],
 *   padding: spacing[4],
 *   borderRadius: borderRadius.md,
 *   boxShadow: shadows.base,
 * };
 */

// 导入所有tokens
import { colors } from './colors';
import { typography } from './typography';
import { spacing } from './spacing';
import { shadows } from './shadows';
import { borderRadius } from './borderRadius';

// 重新导出
export { colors, typography, spacing, shadows, borderRadius };

// 导出类型
export type { Colors } from './colors';
export type { Typography } from './typography';
export type { Spacing } from './spacing';
export type { Shadows } from './shadows';
export type { BorderRadius } from './borderRadius';

// 统一导出对象
export const tokens = {
  colors,
  typography,
  spacing,
  shadows,
  borderRadius,
} as const;

