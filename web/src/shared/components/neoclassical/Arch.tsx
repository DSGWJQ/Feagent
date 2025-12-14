/**
 * 拱形结构组件
 *
 * 模拟古罗马建筑中的拱门结构
 * 为内容提供优雅的建筑感框架
 */

import styles from './Arch.module.css';

export interface ArchProps {
  /** 子内容 */
  children?: React.ReactNode;
  /** 自定义类名 */
  className?: string;
  /** 无障碍标签 */
  label?: string;
}

/**
 * Arch - 拱形建筑结构装饰
 *
 * @example
 * ```tsx
 * <Arch label="古典内容框架">
 *   <h2>标题</h2>
 *   <p>内容文本...</p>
 * </Arch>
 * ```
 */
export function Arch({ children, className, label }: ArchProps) {
  return (
    <div className={[styles.arch, className].filter(Boolean).join(' ')} aria-label={label}>
      <div className={styles.inner}>{children}</div>
    </div>
  );
}

export default Arch;
