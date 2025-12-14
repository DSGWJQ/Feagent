/**
 * 浮雕装饰面板组件
 *
 * 结合石雕质感、装饰边框和黄金分割线
 * 提供优雅的内容展示容器
 */

import styles from './ReliefPanel.module.css';

export interface ReliefPanelProps {
  /** 标题 */
  title?: string;
  /** 内容 */
  children: React.ReactNode;
  /** 自定义类名 */
  className?: string;
}

/**
 * ReliefPanel - 浮雕装饰面板
 *
 * @example
 * ```tsx
 * <ReliefPanel title="古典主题">
 *   <p>在这里展示内容...</p>
 * </ReliefPanel>
 * ```
 */
export function ReliefPanel({ title, children, className }: ReliefPanelProps) {
  return (
    <section className={[styles.panel, className].filter(Boolean).join(' ')}>
      {title && <h2 className={styles.title}>{title}</h2>}
      <div className={styles.rule} />
      <div className={styles.body}>{children}</div>
    </section>
  );
}

export default ReliefPanel;
