# Feagent 设计系统文档

**Version**: 1.0.0
**Last Updated**: 2025-12-14
**Status**: Production Ready ✅

---

## 目录

1. [概述](#概述)
2. [设计原则](#设计原则)
3. [颜色系统](#颜色系统)
4. [间距系统](#间距系统)
5. [排版系统](#排版系统)
6. [阴影与圆角](#阴影与圆角)
7. [使用指南](#使用指南)
8. [最佳实践](#最佳实践)
9. [浏览器兼容性](#浏览器兼容性)

---

## 概述

Feagent设计系统是一套完整的设计token和样式规范，旨在创建统一、专业、易维护的企业级AI Agent平台界面。

### 核心特性

- ✅ **100% Design Token覆盖** - 所有样式值通过token定义
- ✅ **CSS Variables + CSS Modules** - 运行时可修改 + 组件级作用域
- ✅ **无渐变色** - 专业企业风格，避免视觉噪音
- ✅ **Dark Theme优先** - 专为AI平台优化的深色主题
- ✅ **4px网格系统** - 精确的间距控制
- ✅ **语义化命名** - 易于理解和维护
- ✅ **浏览器兼容性** - CSS Variable fallbacks确保跨浏览器支持

### 技术栈

- **Design Tokens**: TypeScript定义，类型安全
- **CSS Variables**: `:root`全局声明，运行时可修改
- **CSS Modules**: 组件级样式隔离
- **Ant Design 5**: 深度主题定制

---

## 设计原则

### 1. 专业科技蓝主色调

主色使用 `#1a7fff` (专业科技蓝)，区别于Ant Design默认蓝色，体现AI平台的科技感。

```css
--color-primary-400: #1a7fff;
```

### 2. 完整的色阶系统 (50-900)

所有颜色提供10级色阶，从浅到深，确保设计灵活性。

```
50 (最浅) → 100 → 200 → 300 → 400 (主色) → 500 → 600 → 700 → 800 → 900 (最深)
```

### 3. 语义化命名

颜色按用途分类：
- **Primary**: 品牌主色
- **Neutral**: 中性灰度
- **Semantic**: 功能性（success/error/warning/info）
- **Accent**: 模块特色（agent/workflow/tool）

### 4. 无渐变色政策

❌ 禁止使用 `linear-gradient`, `radial-gradient`
✅ 使用纯色 + 阴影/边框创建层次感

**为什么？**
- 更专业的企业级外观
- 避免视觉疲劳
- 更好的性能
- 更易维护

---

## 颜色系统

### 主色 (Primary)

专业科技蓝，用于品牌标识、主要操作按钮、链接等。

```typescript
primary: {
  50: '#e6f0ff',   // 背景色、hover状态
  100: '#b3d4ff',
  200: '#80b8ff',
  300: '#4d9bff',
  400: '#1a7fff',  // ⭐ 主色
  500: '#0066e6',
  600: '#0052b3',
  700: '#003d80',
  800: '#00294d',
  900: '#00141a',
}
```

**CSS Variables**:
```css
--color-primary-50 至 --color-primary-900
```

**使用场景**:
- 主要操作按钮背景
- 活动状态指示
- 重要文字高亮
- Logo/品牌元素

---

### 中性色 (Neutral)

灰度系统，用于文字、背景、边框、分割线等。

```typescript
neutral: {
  50: '#fafafa',   // 浅色文字
  100: '#f5f5f5',
  200: '#e8e8e8',  // 边框
  300: '#d1d1d1',
  400: '#9e9e9e',  // 描述文字
  500: '#6b6b6b',
  600: '#4a4a4a',
  700: '#2e2e2e',
  800: '#1a1a1a',  // 深色背景
  900: '#0a0a0a',  // ⭐ 主背景（深色主题）
  white: '#ffffff',
  black: '#000000',
}
```

**CSS Variables**:
```css
--color-neutral-50 至 --color-neutral-900
--color-white, --color-black
```

**使用场景**:
- 文字颜色（50/400/500）
- 背景色（800/900）
- 边框/分割线（200/700/800）
- 卡片容器（800）

---

### 语义色 (Semantic)

功能性颜色，传达状态信息。

```typescript
semantic: {
  success: {
    main: '#10b981',   // 成功绿色
    light: '#34d399',
    dark: '#059669',
    bg: '#d1fae5',
  },
  error: {
    main: '#ef4444',   // 错误红色
    light: '#f87171',
    dark: '#dc2626',
    bg: '#fee2e2',
  },
  warning: {
    main: '#f59e0b',   // 警告黄色
    light: '#fbbf24',
    dark: '#d97706',
    bg: '#fef3c7',
  },
  info: {
    main: '#3b82f6',   // 信息蓝色
    light: '#60a5fa',
    dark: '#2563eb',
    bg: '#dbeafe',
  },
}
```

**CSS Variables**:
```css
--color-success, --color-success-light, --color-success-dark, --color-success-bg
--color-error, --color-error-light, --color-error-dark, --color-error-bg
--color-warning, --color-warning-light, --color-warning-dark, --color-warning-bg
--color-info, --color-info-light, --color-info-dark, --color-info-bg
```

**使用场景**:
| 颜色 | 用途 |
|------|------|
| Success | 成功提示、完成状态、绿色按钮 |
| Error | 错误提示、失败状态、删除按钮 |
| Warning | 警告提示、注意事项、待处理状态 |
| Info | 信息提示、帮助文档、次要操作 |

---

### 辅助色 (Accent)

模块特色颜色，用于区分不同功能模块。

```typescript
accent: {
  agent: '#8b5cf6',         // 紫色 - Agent相关
  workflow: '#06b6d4',      // 青色 - Workflow相关
  tool: '#f97316',          // 橙红 - Tool相关
  notification: '#eb2f96',  // 粉红 - Notification节点
  audio: '#eb2f96',         // 粉红 - Audio节点
}
```

**CSS Variables**:
```css
--color-accent-agent
--color-accent-workflow
--color-accent-tool
--color-accent-notification
--color-accent-audio
```

**使用场景**:
- Agent图标/卡片边框：紫色
- Workflow节点/连接线：青色
- Tool操作按钮/图标：橙红色
- Notification节点：粉红色
- Audio节点：粉红色

---

### 叠加层 (Overlay)

半透明遮罩，用于模态框、遮罩层等。

```typescript
overlay: {
  10: 'rgba(0, 0, 0, 0.1)',  // 极浅遮罩
  20: 'rgba(0, 0, 0, 0.2)',
  30: 'rgba(0, 0, 0, 0.3)',
  40: 'rgba(0, 0, 0, 0.4)',
  50: 'rgba(0, 0, 0, 0.5)',
  60: 'rgba(0, 0, 0, 0.6)',  // ⭐ MiniMap默认
  70: 'rgba(0, 0, 0, 0.7)',
  80: 'rgba(0, 0, 0, 0.8)',
  90: 'rgba(0, 0, 0, 0.9)',  // 深度遮罩
}
```

**CSS Variables**:
```css
--color-overlay-10 至 --color-overlay-90
```

**使用场景**:
- 模态框遮罩：60-80
- MiniMap遮罩：60
- 悬浮提示背景：70-80
- 临时禁用状态：40-50

---

## 间距系统

基于 **4px 网格系统**，确保视觉对齐和一致性。

```typescript
spacing: {
  0: '0px',
  1: '4px',     // 最小间距
  2: '8px',     // 小间距
  3: '12px',
  4: '16px',    // ⭐ 标准间距
  5: '20px',
  6: '24px',    // ⭐ 大间距
  7: '28px',
  8: '32px',    // 卡片内边距
  9: '36px',
  10: '40px',
  11: '44px',
  12: '48px',   // 区块间距
  13: '52px',
  14: '56px',
  15: '60px',
  16: '64px',   // 大区块间距
}
```

**CSS Variables**:
```css
--spacing-0 至 --spacing-16
```

**使用指南**:

| 间距值 | 使用场景 |
|--------|----------|
| 1-2 (4-8px) | 图标与文字间距、紧凑列表项 |
| 3-4 (12-16px) | 按钮内边距、输入框内边距、标准列表项 |
| 5-6 (20-24px) | 卡片内边距、区块标题下边距 |
| 8 (32px) | 大卡片内边距、页面区块间距 |
| 12 (48px) | 页面区块大间距 |
| 16 (64px) | 页面顶部/底部边距 |

**示例**:
```css
/* ✅ 推荐 */
.button {
  padding: var(--spacing-2) var(--spacing-4); /* 8px 16px */
}

/* ❌ 避免 */
.button {
  padding: 10px 18px; /* 不规则数字，破坏网格系统 */
}
```

---

## 排版系统

### 字体家族

```typescript
fontFamily: {
  base: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  code: '"JetBrains Mono", "Fira Code", Consolas, "Courier New", monospace',
}
```

**CSS Variables**:
```css
--font-family-base
--font-family-code
```

**使用场景**:
- `base`: 所有正文、标题、UI文字
- `code`: 代码块、技术参数、JSON显示

---

### 字体大小

```typescript
fontSize: {
  xs: '0.75rem',    // 12px - 辅助信息
  sm: '0.875rem',   // 14px - 描述文字
  base: '1rem',     // 16px - ⭐ 正文（默认）
  lg: '1.125rem',   // 18px - 小标题
  xl: '1.25rem',    // 20px - 卡片标题
  '2xl': '1.5rem',  // 24px - 区块标题
  '3xl': '1.875rem',// 30px - 页面主标题
  '4xl': '2.25rem', // 36px - 大标题
}
```

**CSS Variables**:
```css
--font-size-xs 至 --font-size-4xl
```

**使用指南**:

| 大小 | 用途 | 示例 |
|------|------|------|
| xs (12px) | WebSocket状态、时间戳、版本号 | "实时同步" |
| sm (14px) | 描述文字、表单标签 | "可视化工作流设计器" |
| base (16px) | 正文、按钮文字 | 大部分UI文字 |
| lg (18px) | 小标题 | 列表标题 |
| xl (20px) | 卡片标题 | "Agent详情" |
| 2xl (24px) | 区块标题 | "最近的工作流" |
| 3xl (30px) | 页面主标题 | "AI工作流构建器" |

---

### 字重

```typescript
fontWeight: {
  light: 300,    // 轻量文字
  normal: 400,   // ⭐ 正文（默认）
  medium: 500,   // 次要强调
  semibold: 600, // ⭐ 标题
  bold: 700,     // 强烈强调
}
```

**CSS Variables**:
```css
--font-weight-light 至 --font-weight-bold
```

**使用指南**:
- `normal` (400): 正文、描述
- `semibold` (600): 所有标题、重要标签
- `bold` (700): 特别强调的数字、状态

---

### 行高

```typescript
lineHeight: {
  tight: 1.25,   // 标题
  normal: 1.5,   // ⭐ 正文（默认）
  relaxed: 1.75, // 长文章
}
```

**CSS Variables**:
```css
--line-height-tight, --line-height-normal, --line-height-relaxed
```

---

## 阴影与圆角

### 阴影 (Shadows)

用于创建层次感和深度。

```typescript
shadows: {
  none: 'none',
  sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
  base: '0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)',
  md: '0 4px 6px rgba(0, 0, 0, 0.07), 0 2px 4px rgba(0, 0, 0, 0.05)',
  lg: '0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05)',
  xl: '0 20px 25px rgba(0, 0, 0, 0.1), 0 10px 10px rgba(0, 0, 0, 0.04)',
}
```

**CSS Variables**:
```css
--shadow-none 至 --shadow-xl
```

**使用指南**:

| 阴影 | 用途 | 示例 |
|------|------|------|
| sm | 按钮、输入框 | hover状态 |
| md | 卡片、下拉菜单 | ⭐ 最常用 |
| lg | 模态框、悬浮面板 | 强调层级 |
| xl | 全屏遮罩、重要弹窗 | 最高层级 |

---

### 圆角 (Border Radius)

```typescript
borderRadius: {
  none: '0',
  sm: '4px',     // 小元素
  base: '6px',
  md: '8px',     // ⭐ 标准（按钮、卡片）
  lg: '12px',    // 大卡片
  xl: '16px',    // 特大卡片
  full: '9999px',// 圆形（头像、徽章）
}
```

**CSS Variables**:
```css
--radius-none 至 --radius-full
```

**使用指南**:

| 圆角 | 用途 | 示例 |
|------|------|------|
| sm (4px) | 输入框、小按钮 | 标签、徽章 |
| md (8px) | 标准按钮、卡片 | ⭐ 默认值 |
| lg (12px) | 大卡片、容器 | 工作流节点 |
| full | 圆形元素 | 头像、状态点 |

---

## 使用指南

### 在CSS中使用

**推荐方式 - CSS Variables**:
```css
.my-component {
  background-color: var(--color-neutral-900);
  color: var(--color-neutral-50);
  padding: var(--spacing-4);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  font-size: var(--font-size-base);
}
```

**带fallback的用法**:
```css
.my-component {
  /* 推荐：提供fallback以增强兼容性 */
  background-color: var(--color-primary-400, #1a7fff);

  /* SVG/Canvas中必须使用fallback */
  stroke: var(--color-neutral-600, #4a4a4a);
}
```

---

### 在TypeScript中使用

**导入tokens**:
```typescript
import { colors, spacing, typography } from '@/shared/styles/tokens';

// 使用
const buttonStyle = {
  backgroundColor: colors.primary[400],
  padding: `${spacing[2]} ${spacing[4]}`,
  fontSize: typography.fontSize.base,
};
```

**注意**: 在TypeScript中使用tokens时，无法享受运行时主题切换的好处。优先使用CSS Variables。

---

### 在Ant Design组件中使用

**通过theme配置**:
```typescript
import { theme } from '@/shared/styles/theme';

<ConfigProvider theme={theme}>
  <App />
</ConfigProvider>
```

**自定义样式覆盖**:
```tsx
<Button
  type="primary"
  style={{
    backgroundColor: 'var(--color-primary-400)',
    borderColor: 'var(--color-primary-400)',
  }}
>
  主要操作
</Button>
```

---

## 最佳实践

### ✅ DO（推荐）

1. **始终使用CSS Variables**
   ```css
   background: var(--color-neutral-900);
   ```

2. **SVG中添加fallbacks**
   ```css
   stroke: var(--color-primary-400, #1a7fff);
   ```

3. **使用间距token**
   ```css
   padding: var(--spacing-4) var(--spacing-6);
   ```

4. **语义化颜色命名**
   ```css
   /* ✅ 清晰的用途 */
   border-color: var(--color-neutral-800);
   ```

5. **遵循4px网格**
   ```css
   margin-bottom: var(--spacing-3); /* 12px */
   ```

---

### ❌ DON'T（避免）

1. **避免hardcoded颜色**
   ```css
   /* ❌ */
   background: #1a1a1a;

   /* ✅ */
   background: var(--color-neutral-800);
   ```

2. **避免渐变色**
   ```css
   /* ❌ 违反设计原则 */
   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

   /* ✅ 使用纯色+阴影 */
   background: var(--color-primary-400);
   box-shadow: var(--shadow-md);
   ```

3. **避免不规则间距**
   ```css
   /* ❌ */
   padding: 10px 18px;

   /* ✅ */
   padding: var(--spacing-2) var(--spacing-4); /* 8px 16px */
   ```

4. **避免magic numbers**
   ```css
   /* ❌ */
   font-size: 19px;

   /* ✅ */
   font-size: var(--font-size-lg); /* 18px */
   ```

5. **避免inline styles（除非必要）**
   ```tsx
   {/* ❌ */}
   <div style={{ color: '#fafafa', padding: '16px' }}>

   {/* ✅ 使用CSS Module */}
   <div className={styles.container}>
   ```

---

## 浏览器兼容性

### CSS Variables支持

**支持的浏览器**:
- Chrome 49+
- Firefox 31+
- Safari 9.1+
- Edge 15+
- iOS Safari 9.3+
- Android Chrome 49+

### Fallback策略

对于非evergreen浏览器或WebView，使用fallback值：

```css
/* 标准用法 */
color: var(--color-primary-400);

/* 带fallback（推荐） */
color: var(--color-primary-400, #1a7fff);
```

**SVG/Canvas中必须使用fallback**：
```typescript
// MiniMap nodeColor
case 'textModel':
  return 'var(--color-primary-400, #1a7fff)';
```

---

## 文件位置

```
web/src/shared/styles/
├── tokens/
│   ├── colors.ts          # 颜色token定义
│   ├── spacing.ts         # 间距token定义
│   ├── typography.ts      # 排版token定义
│   ├── shadows.ts         # 阴影token定义
│   ├── borderRadius.ts    # 圆角token定义
│   └── index.ts           # 统一导出
├── global.css             # CSS Variables声明
└── theme.ts               # Ant Design主题配置
```

---

## 版本历史

### v1.0.0 (2025-12-14)

**新增**:
- ✅ 完整的设计token系统
- ✅ Primary/Neutral/Semantic/Accent颜色系统
- ✅ Overlay透明度系统
- ✅ 4px间距网格系统
- ✅ 排版系统（字体、大小、字重、行高）
- ✅ 阴影与圆角系统
- ✅ CSS Variables全局声明
- ✅ Ant Design 5主题深度定制
- ✅ @xyflow/react主题定制
- ✅ 浏览器兼容性fallbacks

**设计决策**:
- ❌ 无渐变色政策（企业级专业外观）
- ✅ Dark Theme优先（AI平台优化）
- ✅ 专业科技蓝主色调（#1a7fff）
- ✅ 100% CSS Variables覆盖

---

## 相关文档

- [组件开发指南](./COMPONENT_DEVELOPMENT_GUIDE.md)
- [样式迁移Checklist](./STYLE_MIGRATION_CHECKLIST.md)
- [CSS Module使用指南](./CSS_MODULE_GUIDE.md)
- [代码示例集](./STYLE_EXAMPLES.md)

---

**维护者**: Feagent Frontend Team
**联系**: 如有疑问或建议，请提交Issue
