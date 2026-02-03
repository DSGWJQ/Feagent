/**
 * ThemeToggle组件
 *
 * 带动画效果的主题切换按钮
 * 显示Sun/Moon图标，带有平滑过渡动画
 */

import { BulbOutlined, BulbFilled } from '@ant-design/icons';
import { useTheme } from '../contexts/ThemeContext';
import styles from './ThemeToggle.module.css';

interface ThemeToggleProps {
  className?: string;
  showTooltip?: boolean;
}

/**
 * ThemeToggle - 主题切换按钮
 *
 * @example
 * ```tsx
 * <ThemeToggle showTooltip />
 * ```
 */
export function ThemeToggle({ className, showTooltip = true }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();

  const isDark = theme === 'dark';
  const tooltipText = isDark ? '切换到浅色模式' : '切换到深色模式';

  return (
    <button
      className={`${styles.toggleButton} ${className || ''}`}
      onClick={toggleTheme}
      aria-label={tooltipText}
      data-tooltip={showTooltip ? tooltipText : undefined}
      type="button"
    >
      <div className={styles.iconWrapper}>
        {/* Sun图标 (Dark模式) */}
        <BulbOutlined
          className={`${styles.icon} ${styles.sunIcon} ${!isDark ? styles.hidden : ''}`}
        />

        {/* Moon图标 (Light模式) */}
        <BulbFilled
          className={`${styles.icon} ${styles.moonIcon} ${!isDark ? styles.visible : ''}`}
        />
      </div>
    </button>
  );
}

export default ThemeToggle;
