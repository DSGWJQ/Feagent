/**
 * 新古典主义色彩系统
 *
 * 设计理念：
 * - 古希腊罗马建筑的永恒美学
 * - 大理石白与深邃石墨的对比
 * - 古典金与皇家蓝的装饰色
 * - 支持Dark/Light主题切换
 */

export const neoclassicalColors = {
  /**
   * 核心调色板
   */
  palette: {
    elegantGreyWhite: '#F9FAFB',  // 典雅灰白
    deepGraphite: '#374151',       // 深邃石墨
    classicalGold: '#D97706',      // 古典金
    royalBlue: '#1E40AF',          // 皇家蓝
    marbleWhite: '#FFFFFF',        // 大理石白
    shadowGrey: '#6B7280',         // 阴影灰
    imperialRed: '#DC2626',        // 帝国红
  },

  /**
   * 色阶系统
   */
  scale: {
    // 中性色（marble/graphite系列）
    neutral: {
      50: '#F9FAFB',
      100: '#F3F4F6',
      200: '#E5E7EB',
      300: '#D1D5DB',
      400: '#9CA3AF',
      500: '#6B7280',
      600: '#4B5563',
      700: '#374151',
      800: '#1F2937',
      900: '#111827',
      950: '#0B1220',
      white: '#FFFFFF',
      black: '#000000',
    },

    // 皇家蓝系列
    royalBlue: {
      50: '#EFF6FF',
      100: '#DBEAFE',
      200: '#BFDBFE',
      300: '#93C5FD',
      400: '#60A5FA',
      500: '#3B82F6',
      600: '#2563EB',
      700: '#1D4ED8',
      800: '#1E40AF',
      900: '#1E3A8A',
    },

    // 古典金系列
    gold: {
      50: '#FFFBEB',
      100: '#FEF3C7',
      200: '#FDE68A',
      300: '#FCD34D',
      400: '#FBBF24',
      500: '#F59E0B',
      600: '#D97706',
      700: '#B45309',
      800: '#92400E',
      900: '#78350F',
    },

    // 帝国红系列
    imperialRed: {
      50: '#FEF2F2',
      100: '#FEE2E2',
      200: '#FECACA',
      300: '#FCA5A5',
      400: '#F87171',
      500: '#EF4444',
      600: '#DC2626',
      700: '#B91C1C',
      800: '#991B1B',
      900: '#7F1D1D',
    },
  },

  /**
   * 语义色系统
   */
  semantic: {
    success: {
      main: '#15803D',
      light: '#22C55E',
      dark: '#166534',
      bg: '#DCFCE7'
    },
    warning: {
      main: '#D97706',  // 使用古典金
      light: '#F59E0B',
      dark: '#B45309',
      bg: '#FEF3C7'
    },
    error: {
      main: '#DC2626',  // 使用帝国红
      light: '#EF4444',
      dark: '#B91C1C',
      bg: '#FEE2E2'
    },
    info: {
      main: '#1E40AF',  // 使用皇家蓝
      light: '#3B82F6',
      dark: '#1E3A8A',
      bg: '#DBEAFE'
    },
  },

  /**
   * 遮罩层系统
   */
  overlay: {
    10: 'rgba(0, 0, 0, 0.10)',
    20: 'rgba(0, 0, 0, 0.20)',
    30: 'rgba(0, 0, 0, 0.30)',
    40: 'rgba(0, 0, 0, 0.40)',
    50: 'rgba(0, 0, 0, 0.50)',
    60: 'rgba(0, 0, 0, 0.60)',
    70: 'rgba(0, 0, 0, 0.70)',
    80: 'rgba(0, 0, 0, 0.80)',
    90: 'rgba(0, 0, 0, 0.90)',
  },

  /**
   * 主题变量映射（Dark/Light）
   */
  themeVars: {
    light: {
      '--neo-bg': '#FFFFFF',          // 大理石白背景
      '--neo-surface': '#F9FAFB',     // 典雅灰白表面
      '--neo-surface-2': '#F3F4F6',   // 次级表面
      '--neo-text': '#374151',        // 深邃石墨文字
      '--neo-text-2': '#6B7280',      // 阴影灰次级文字
      '--neo-border': '#E5E7EB',      // 边框
      '--neo-gold': '#D97706',        // 古典金装饰
      '--neo-blue': '#1E40AF',        // 皇家蓝装饰
      '--neo-red': '#DC2626',         // 帝国红强调
      '--neo-focus': '#1E40AF',       // 焦点颜色
    },
    dark: {
      '--neo-bg': '#0B1220',          // 深邃背景
      '--neo-surface': '#111827',     // 石墨表面
      '--neo-surface-2': '#1F2937',   // 次级表面
      '--neo-text': '#F9FAFB',        // 典雅灰白文字
      '--neo-text-2': '#CBD5E1',      // 次级文字
      '--neo-border': '#374151',      // 深邃石墨边框
      '--neo-gold': '#D97706',        // 古典金（保持）
      '--neo-blue': '#60A5FA',        // 皇家蓝（提亮对比）
      '--neo-red': '#EF4444',         // 帝国红（提亮）
      '--neo-focus': '#F59E0B',       // 金色焦点
    },
  },
} as const;

export type NeoclassicalColors = typeof neoclassicalColors;
