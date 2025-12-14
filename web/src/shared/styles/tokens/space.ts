/**
 * 黄金比例间距系统
 *
 * 基于Fibonacci数列（近似黄金比例φ≈1.618）
 * 用于padding/margin/gap，确保视觉和谐
 *
 * 数列：0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89...
 *
 * 注意：此系统专用于padding/margin/gap
 * 固定高度/宽度请继续使用现有spacing系统以保证向后兼容
 */

export const space = {
  /** 0px - 无间距 */
  0: '0px',

  /** 2px - 最小装饰性间距 */
  1: '2px',

  /** 3px - 细微分隔 */
  2: '3px',

  /** 5px - 小间距 */
  3: '5px',

  /** 8px - 基础间距（黄金比例起点） */
  4: '8px',

  /** 13px - 标准内边距 */
  5: '13px',

  /** 21px - 中等间距（φ² × base） */
  6: '21px',

  /** 34px - 大间距（φ³ × base） */
  7: '34px',

  /** 55px - 特大间距（φ⁴ × base） */
  8: '55px',

  /** 89px - 超大间距（φ⁵ × base）- 用于章节分隔 */
  9: '89px',
} as const;

export type Space = typeof space;

/**
 * 黄金比例常量
 */
export const PHI = 1.618033988749895;

/**
 * 基于黄金比例计算间距
 *
 * @param base 基础值（默认8px）
 * @param power 黄金比例的幂次
 * @returns 计算后的间距值
 *
 * @example
 * ```typescript
 * calculateGoldenSpace(8, 2); // 8 * φ² ≈ 21px
 * calculateGoldenSpace(8, 3); // 8 * φ³ ≈ 34px
 * ```
 */
export function calculateGoldenSpace(base: number = 8, power: number = 1): number {
  return Math.round(base * Math.pow(PHI, power));
}
