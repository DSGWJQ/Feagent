/**
 * 古典柱式组件
 *
 * 支持三种古典柱式：
 * - Doric (多立克): 简洁有力，无装饰
 * - Ionic (爱奥尼亚): 优雅精致，带涡卷装饰
 * - Corinthian (科林斯): 华丽繁复，顶部装饰丰富
 */

import styles from './Column.module.css';

export type ColumnOrder = 'doric' | 'ionic' | 'corinthian';

export interface ColumnProps {
  /** 柱式类型 */
  order?: ColumnOrder;
  /** 高度（px） */
  height?: number;
  /** 宽度（px） */
  width?: number;
  /** 无障碍标签 */
  label?: string;
  /** 自定义类名 */
  className?: string;
}

/**
 * Column - 古典柱式装饰组件
 *
 * @example
 * ```tsx
 * <Column order="corinthian" height={240} width={60} />
 * ```
 */
export function Column({
  order = 'doric',
  height = 220,
  width = 56,
  label,
  className,
}: ColumnProps) {
  return (
    <div
      className={[styles.column, styles[order], className].filter(Boolean).join(' ')}
      style={{ height, width }}
      role={label ? 'img' : undefined}
      aria-label={label}
    />
  );
}

export default Column;
