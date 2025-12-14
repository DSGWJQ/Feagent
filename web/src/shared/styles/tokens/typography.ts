/**
 * 设计系统 - 字体Typography Token
 *
 * 设计原则：
 * - 使用系统字体栈
 * - 完整的字号系统（12px-36px）
 * - 清晰的字重层级
 * - 新古典主义：支持古典serif字体和黄金比例缩放
 */

/**
 * 黄金比例常量
 * φ (phi) = 1.618033988749895
 * √φ = 1.272 (用于字体缩放，更适合UI)
 */
const PHI_SQRT = 1.272;

export const typography = {
  // 字体族
  fontFamily: {
    base: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif',
    code: '"JetBrains Mono", "Fira Code", Consolas, "Liberation Mono", "Courier New", monospace',
    serif: '"Iowan Old Style", "Palatino Linotype", Palatino, Garamond, Georgia, "Times New Roman", Times, serif',
  },

  // 字号（基于16px基准）
  fontSize: {
    xs: '0.75rem',      // 12px
    sm: '0.875rem',     // 14px
    base: '1rem',       // 16px
    lg: '1.125rem',     // 18px
    xl: '1.25rem',      // 20px
    '2xl': '1.5rem',    // 24px
    '3xl': '1.875rem',  // 30px
    '4xl': '2.25rem',   // 36px
  },

  // 新古典主义字号（基于黄金比例√φ = 1.272）
  // 基准14px，通过√φ的幂次缩放
  neoclassicalFontSize: {
    xs: '0.864rem',     // 14px / φ ≈ 13.82px → 0.864rem
    sm: '0.988rem',     // 14px / √φ ≈ 15.81px → 0.988rem
    base: '0.875rem',   // 14px (基准)
    lg: '1.113rem',     // 14px * √φ ≈ 17.81px → 1.113rem
    xl: '1.415rem',     // 14px * φ ≈ 22.65px → 1.415rem
    '2xl': '1.800rem',  // 14px * φ^1.5 ≈ 28.80px → 1.800rem
    '3xl': '2.290rem',  // 14px * φ^2 ≈ 36.64px → 2.290rem
  },

  // 字重
  fontWeight: {
    light: 300,
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },

  // 行高
  lineHeight: {
    tight: 1.25,
    normal: 1.5,
    relaxed: 1.75,
    loose: 2,
    golden: 1.618,  // 黄金比例行高（新古典主义）
  },

  // 字间距（letter-spacing）
  letterSpacing: {
    tighter: '-0.05em',
    tight: '-0.025em',
    normal: '0',
    wide: '0.025em',
    wider: '0.05em',
    widest: '0.1em',
    classical: '0.02em',  // 古典文字建议间距
  },
} as const;

export type Typography = typeof typography;

/**
 * 计算基于黄金比例的字体大小
 *
 * @param base 基础字号（px）
 * @param power √φ的幂次
 * @returns rem值
 *
 * @example
 * ```typescript
 * calculateGoldenFontSize(14, 2); // 14 * (√φ)^2 ≈ 22.65px
 * ```
 */
export function calculateGoldenFontSize(base: number = 14, power: number = 1): string {
  const px = base * Math.pow(PHI_SQRT, power);
  return `${(px / 16).toFixed(3)}rem`;
}
