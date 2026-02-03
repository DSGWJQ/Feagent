/**
 * Ant Design 主题配置
 *
 * 基于设计Token系统构建
 * 提供完整的企业级UI主题定制
 * 支持新古典主义设计系统（通过CSS Variables动态响应主题切换）
 */

import type { ThemeConfig } from 'antd';
import { colors, typography, spacing, shadows, borderRadius } from './tokens';
import { neoclassicalColors } from './tokens/neoclassicalColors';

export const theme: ThemeConfig = {
  token: {
    // ========== 颜色系统（新古典主义） ==========
    // 使用古典金作为主色（替代原来的蓝色）
    colorPrimary: neoclassicalColors.palette.classicalGold,
    colorSuccess: colors.semantic.success.main,
    colorWarning: neoclassicalColors.palette.classicalGold, // 使用古典金
    colorError: neoclassicalColors.palette.imperialRed,     // 使用帝国红
    colorInfo: neoclassicalColors.palette.royalBlue,         // 使用皇家蓝

    colorLink: neoclassicalColors.palette.royalBlue,
    colorLinkHover: neoclassicalColors.scale.royalBlue[700],
    colorLinkActive: neoclassicalColors.scale.royalBlue[800],

    // 背景色（使用neutral scale）
    colorBgContainer: neoclassicalColors.scale.neutral.white,
    colorBgLayout: neoclassicalColors.scale.neutral[100],
    colorBgElevated: neoclassicalColors.scale.neutral.white,
    colorBorder: neoclassicalColors.scale.neutral[200],
    colorBorderSecondary: neoclassicalColors.scale.neutral[100],

    // 文字色
    colorText: neoclassicalColors.scale.neutral[900],
    colorTextSecondary: neoclassicalColors.scale.neutral[600],
    colorTextTertiary: neoclassicalColors.scale.neutral[400],
    colorTextQuaternary: neoclassicalColors.scale.neutral[300],

    // ========== 字体系统（新古典主义） ==========
    fontFamily: typography.fontFamily.serif, // 使用serif字体族
    fontSize: 14,
    fontSizeHeading1: 30,
    fontSizeHeading2: 24,
    fontSizeHeading3: 20,
    fontSizeHeading4: 18,
    fontSizeHeading5: 16,

    // ========== 圆角系统 ==========
    borderRadius: parseInt(borderRadius.base),
    borderRadiusLG: parseInt(borderRadius.md),
    borderRadiusSM: parseInt(borderRadius.sm),
    borderRadiusXS: parseInt(borderRadius.sm),

    // ========== 间距系统 ==========
    padding: parseInt(spacing[4]),
    paddingLG: parseInt(spacing[6]),
    paddingSM: parseInt(spacing[2]),
    paddingXS: parseInt(spacing[1]),

    margin: parseInt(spacing[4]),
    marginLG: parseInt(spacing[6]),
    marginSM: parseInt(spacing[2]),
    marginXS: parseInt(spacing[1]),

    // ========== 阴影系统 ==========
    boxShadow: shadows.base,
    boxShadowSecondary: shadows.sm,
  },

  // ========== 组件特定配置 ==========
  components: {
    // Layout 布局
    Layout: {
      headerBg: neoclassicalColors.scale.neutral.white,
      headerPadding: `0 ${spacing[6]}`,
      siderBg: neoclassicalColors.scale.neutral.white,
      bodyBg: neoclassicalColors.scale.neutral[100],
      footerBg: neoclassicalColors.scale.neutral[50],
    },

    // Menu 菜单
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: `${neoclassicalColors.palette.classicalGold}10`,
      itemSelectedColor: neoclassicalColors.palette.classicalGold,
      itemActiveBg: neoclassicalColors.scale.neutral[50],
      itemHoverBg: neoclassicalColors.scale.neutral[50],
      itemBorderRadius: parseInt(borderRadius.base),
    },

    // Button 按钮（新古典主义）
    Button: {
      // 基础配置
      primaryColor: neoclassicalColors.scale.neutral.white,
      defaultBg: neoclassicalColors.scale.neutral.white,
      defaultBorderColor: neoclassicalColors.scale.neutral[200],
      borderRadius: parseInt(borderRadius.md),
      controlHeight: 32,
      controlHeightLG: 40,
      controlHeightSM: 24,

      // Primary按钮状态（古典金）
      colorPrimaryHover: neoclassicalColors.scale.gold[700],
      colorPrimaryActive: neoclassicalColors.scale.gold[800],
      colorPrimaryBorder: neoclassicalColors.palette.classicalGold,

      // Default按钮状态
      defaultColor: neoclassicalColors.scale.neutral[900],
      defaultHoverBg: neoclassicalColors.scale.neutral[50],
      defaultHoverColor: neoclassicalColors.palette.royalBlue,
      defaultHoverBorderColor: neoclassicalColors.palette.royalBlue,
      defaultActiveBg: neoclassicalColors.scale.neutral[100],
      defaultActiveBorderColor: neoclassicalColors.scale.royalBlue[700],

      // Danger按钮（帝国红）
      dangerColor: neoclassicalColors.scale.neutral.white,
      colorErrorHover: neoclassicalColors.scale.imperialRed[400],
      colorErrorActive: neoclassicalColors.scale.imperialRed[700],

      // Text按钮
      textHoverBg: neoclassicalColors.scale.neutral[50],

      // Link按钮
      linkHoverBg: 'transparent',

      // Ghost按钮
      ghostBg: 'transparent',

      // 阴影（新古典效果）
      primaryShadow: `0 2px 0 ${neoclassicalColors.palette.classicalGold}20`,
      dangerShadow: `0 2px 0 ${neoclassicalColors.palette.imperialRed}20`,
    },

    // Card 卡片
    Card: {
      borderRadius: parseInt(borderRadius.md),
      boxShadow: shadows.sm,
    },

    // Input 输入框
    Input: {
      borderRadius: parseInt(borderRadius.base),
      paddingBlock: parseInt(spacing[2]),
      paddingInline: parseInt(spacing[3]),
      activeBorderColor: neoclassicalColors.palette.royalBlue,
      hoverBorderColor: neoclassicalColors.palette.royalBlue,
    },
    Select: {
      borderRadius: parseInt(borderRadius.base),
      colorPrimary: neoclassicalColors.palette.royalBlue, // Focus/Select color
      colorPrimaryHover: neoclassicalColors.scale.royalBlue[400],
    },
    DatePicker: {
      borderRadius: parseInt(borderRadius.base),
      colorPrimary: neoclassicalColors.palette.royalBlue,
      activeBorderColor: neoclassicalColors.palette.royalBlue,
      hoverBorderColor: neoclassicalColors.palette.royalBlue,
    },

    // Table 表格
    Table: {
      headerBg: neoclassicalColors.scale.neutral[50],
      headerColor: neoclassicalColors.scale.neutral[900],
      borderColor: neoclassicalColors.scale.neutral[200],
      rowHoverBg: neoclassicalColors.scale.neutral[50],
    },

    // Modal 模态框
    Modal: {
      borderRadius: parseInt(borderRadius.lg),
      headerBg: neoclassicalColors.scale.neutral.white,
      contentBg: neoclassicalColors.scale.neutral.white,
    },

    // Tag 标签
    Tag: {
      borderRadius: parseInt(borderRadius.base),
    },

    // Badge 徽章
    Badge: {
      dotSize: 6,
    },

    // Tooltip 提示框
    Tooltip: {
      borderRadius: parseInt(borderRadius.sm),
    },

    // Notification 通知
    Notification: {
      borderRadius: parseInt(borderRadius.md),
    },

    // Message 消息
    Message: {
      borderRadius: parseInt(borderRadius.md),
    },
  },
};
