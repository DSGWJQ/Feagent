# 样式迁移 Checklist

**Version**: 1.0.0
**Last Updated**: 2025-12-14

---

## 迁移前准备

### ✅ 阅读文档
- [ ] 阅读 [设计系统文档](./DESIGN_SYSTEM.md)
- [ ] 阅读 [组件开发指南](./COMPONENT_DEVELOPMENT_GUIDE.md)
- [ ] 熟悉可用的CSS Variables

### ✅ 环境准备
- [ ] 确保项目依赖已安装 (`pnpm install`)
- [ ] 确认TypeScript配置支持CSS Modules
- [ ] 准备好测试环境

---

## 迁移步骤

### 1. 分析现有组件

- [ ] 识别所有inline styles
- [ ] 识别hardcoded颜色 (#xxx, rgb(), rgba())
- [ ] 识别hardcoded间距 (px, rem数值)
- [ ] 识别渐变色 (linear-gradient, radial-gradient)
- [ ] 记录组件状态 (hover, active, disabled, focus)

**工具**:
```bash
# 搜索hardcoded颜色
grep -r "#[0-9a-fA-F]\{3,6\}" src/

# 搜索rgba
grep -r "rgba(" src/

# 搜索linear-gradient
grep -r "linear-gradient" src/
```

---

### 2. 创建CSS Module文件

- [ ] 在组件同目录创建 `.module.css` 文件
- [ ] 命名规范：`ComponentName.module.css`
- [ ] 添加文件头注释

```css
/**
 * ComponentName样式
 * 使用CSS Module + 设计Token系统
 */
```

---

### 3. 替换颜色

#### 主色 (Primary)
- [ ] `#1a7fff` → `var(--color-primary-400)`
- [ ] `#0066e6` → `var(--color-primary-500)`
- [ ] 其他主色 → 对应的`--color-primary-{50-900}`

#### 中性色 (Neutral)
- [ ] `#0a0a0a` / `#141414` → `var(--color-neutral-900)`
- [ ] `#1a1a1a` → `var(--color-neutral-800)`
- [ ] `#2e2e2e` / `#262626` → `var(--color-neutral-700)`
- [ ] `#4a4a4a` / `#434343` → `var(--color-neutral-600)`
- [ ] `#6b6b6b` → `var(--color-neutral-500)`
- [ ] `#9e9e9e` / `#8c8c8c` → `var(--color-neutral-400)`
- [ ] `#fafafa` → `var(--color-neutral-50)`
- [ ] `#ffffff` → `var(--color-white)`

#### 语义色 (Semantic)
- [ ] `#10b981` / `#52c41a` → `var(--color-success)`
- [ ] `#ef4444` / `#f5222d` → `var(--color-error)`
- [ ] `#f59e0b` / `#faad14` → `var(--color-warning)`
- [ ] `#3b82f6` / `#1890ff` → `var(--color-info)`

#### 辅助色 (Accent)
- [ ] `#8b5cf6` → `var(--color-accent-agent)`
- [ ] `#06b6d4` → `var(--color-accent-workflow)`
- [ ] `#f97316` → `var(--color-accent-tool)`
- [ ] `#eb2f96` → `var(--color-accent-notification)` / `var(--color-accent-audio)`

#### 透明色 (Overlay)
- [ ] `rgba(0, 0, 0, 0.1)` → `var(--color-overlay-10)`
- [ ] `rgba(0, 0, 0, 0.2)` → `var(--color-overlay-20)`
- [ ] `rgba(0, 0, 0, 0.6)` → `var(--color-overlay-60)`
- [ ] ...其他透明度

---

### 4. 替换间距

#### Padding
- [ ] `4px` → `var(--spacing-1)`
- [ ] `8px` → `var(--spacing-2)`
- [ ] `12px` → `var(--spacing-3)`
- [ ] `16px` → `var(--spacing-4)`
- [ ] `24px` → `var(--spacing-6)`
- [ ] `32px` → `var(--spacing-8)`
- [ ] `48px` → `var(--spacing-12)`

#### Margin
- [ ] 同padding规则

#### Gap (Flexbox/Grid)
- [ ] 同padding规则

#### 不规则间距调整
- [ ] `10px` → `var(--spacing-2)` (8px) 或 `var(--spacing-3)` (12px)
- [ ] `18px` → `var(--spacing-4)` (16px) 或 `var(--spacing-5)` (20px)
- [ ] 对齐到4px网格

---

### 5. 替换排版

#### 字体大小
- [ ] `12px` / `0.75rem` → `var(--font-size-xs)`
- [ ] `14px` / `0.875rem` → `var(--font-size-sm)`
- [ ] `16px` / `1rem` → `var(--font-size-base)`
- [ ] `18px` / `1.125rem` → `var(--font-size-lg)`
- [ ] `20px` / `1.25rem` → `var(--font-size-xl)`
- [ ] `24px` / `1.5rem` → `var(--font-size-2xl)`
- [ ] `30px` / `1.875rem` → `var(--font-size-3xl)`

#### 字重
- [ ] `300` → `var(--font-weight-light)`
- [ ] `400` / `normal` → `var(--font-weight-normal)`
- [ ] `500` → `var(--font-weight-medium)`
- [ ] `600` → `var(--font-weight-semibold)`
- [ ] `700` / `bold` → `var(--font-weight-bold)`

#### 字体家族
- [ ] `-apple-system, ...` → `var(--font-family-base)`
- [ ] `monospace / Consolas / ...` → `var(--font-family-code)`

---

### 6. 替换阴影与圆角

#### 阴影
- [ ] `box-shadow: 0 1px 2px ...` → `var(--shadow-sm)`
- [ ] `box-shadow: 0 4px 6px ...` → `var(--shadow-md)`
- [ ] `box-shadow: 0 10px 15px ...` → `var(--shadow-lg)`
- [ ] `box-shadow: 0 20px 25px ...` → `var(--shadow-xl)`

#### 圆角
- [ ] `4px` → `var(--radius-sm)`
- [ ] `6px` → `var(--radius-base)`
- [ ] `8px` → `var(--radius-md)`
- [ ] `12px` → `var(--radius-lg)`
- [ ] `16px` → `var(--radius-xl)`
- [ ] `9999px / 50%` → `var(--radius-full)`

---

### 7. 移除渐变色

#### 检查
- [ ] 搜索 `linear-gradient(`
- [ ] 搜索 `radial-gradient(`
- [ ] 搜索 `background: ...gradient...`

#### 替换策略
```css
/* ❌ 渐变 */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* ✅ 纯色 + 阴影 */
background: var(--color-primary-400);
box-shadow: var(--shadow-md);
border: 1px solid var(--color-neutral-700);
```

---

### 8. 添加SVG Fallbacks

#### 检查所有SVG相关颜色
- [ ] `<circle fill="..." />`
- [ ] `<path stroke="..." />`
- [ ] ReactFlow `connectionLineStyle`
- [ ] ReactFlow `defaultEdgeOptions`
- [ ] ReactFlow `Background` color
- [ ] ReactFlow `MiniMap` nodeColor / maskColor

#### 添加fallback
```tsx
// ❌ 无fallback
<circle fill="var(--color-primary-400)" />

// ✅ 有fallback
<circle fill="var(--color-primary-400, #1a7fff)" />
```

---

### 9. 更新组件JSX

#### 导入CSS Module
```tsx
import styles from './ComponentName.module.css';
```

#### 替换inline style
```tsx
// ❌ Before
<div style={{ padding: '16px', backgroundColor: '#0a0a0a' }}>

// ✅ After
<div className={styles.container}>
```

#### 条件class
```tsx
<div className={`${styles.card} ${isActive ? styles.active : ''}`}>
```

---

### 10. 处理第三方组件

#### Ant Design
- [ ] 优先使用 `theme` 配置
- [ ] 必要时使用 `:global()` 选择器
- [ ] 或使用 `className` + `!important`

#### ReactFlow
- [ ] 使用 `:global(.react-flow__*)` 选择器
- [ ] 添加 `defaultEdgeOptions` 和 `connectionLineStyle`
- [ ] 定制 `MiniMap` 和 `Controls`

---

## 迁移后验证

### ✅ 功能测试
- [ ] 组件正常渲染
- [ ] 交互功能正常（click, hover, focus）
- [ ] 状态切换正常（loading, disabled）
- [ ] 响应式布局正常

### ✅ 样式测试
- [ ] 颜色显示正确
- [ ] 间距对齐正确
- [ ] 字体大小/字重正确
- [ ] 阴影/圆角显示正常
- [ ] 无渐变色残留

### ✅ 兼容性测试
- [ ] Chrome测试通过
- [ ] Firefox测试通过
- [ ] Safari测试通过
- [ ] Edge测试通过

### ✅ 性能测试
- [ ] 组件渲染性能未下降
- [ ] 无console warnings
- [ ] CSS Module class names生成正确

### ✅ 代码质量
- [ ] TypeScript类型检查通过 (`pnpm type-check`)
- [ ] Lint检查通过 (`pnpm lint`)
- [ ] 无unused CSS classes

---

## 常见问题排查

### 问题1: CSS Variables不生效

**检查**:
- [ ] 是否拼写错误
- [ ] 是否在 `global.css` 中定义
- [ ] 浏览器DevTools中查看computed值

**解决**:
```css
/* ✅ 添加fallback */
color: var(--color-primary-400, #1a7fff);
```

---

### 问题2: CSS Module class未应用

**检查**:
- [ ] 文件名是否为 `.module.css`
- [ ] 是否正确导入 `import styles from './...module.css'`
- [ ] 是否正确应用 `className={styles.xxx}`

---

### 问题3: 样式被第三方组件覆盖

**解决方案**:
```css
/* 方案1: 增加选择器权重 */
.myButton.myButton {
  background: var(--color-primary-400);
}

/* 方案2: 使用!important */
.myButton {
  background: var(--color-primary-400) !important;
}

/* 方案3: 使用:global() */
.wrapper :global(.ant-btn-primary) {
  background: var(--color-primary-400);
}
```

---

### 问题4: SVG颜色显示为黑色

**原因**: CSS Variable在SVG中不支持或未加载

**解决**: 添加fallback
```tsx
<path fill="var(--color-primary-400, #1a7fff)" />
```

---

## 迁移优先级

### P0 (最高优先级)
- [ ] 页面入口组件 (Layout, App)
- [ ] 共享组件 (Button, Card, Modal)
- [ ] 关键业务组件 (Login, Dashboard)

### P1 (高优先级)
- [ ] 工作流相关组件
- [ ] Agent相关组件
- [ ] Tool相关组件

### P2 (中优先级)
- [ ] 设置页面
- [ ] 详情页面
- [ ] 列表页面

### P3 (低优先级)
- [ ] 文档页面
- [ ] 帮助页面
- [ ] 其他辅助页面

---

## 完成标志

### ✅ 代码层面
- [ ] 无hardcoded颜色
- [ ] 无hardcoded间距（除特殊情况）
- [ ] 无渐变色
- [ ] 所有inline styles移至CSS Module
- [ ] SVG颜色有fallbacks

### ✅ 测试层面
- [ ] 所有现有测试通过
- [ ] 新增测试覆盖迁移的组件
- [ ] 跨浏览器测试通过

### ✅ 文档层面
- [ ] 更新组件文档
- [ ] 更新README (如需要)
- [ ] 记录迁移说明 (如有特殊处理)

---

## 示例：完整迁移流程

### Before (旧代码)

```tsx
// MyComponent.tsx
function MyComponent({ title }: Props) {
  return (
    <div style={{
      padding: '16px 24px',
      backgroundColor: '#0a0a0a',
      borderRadius: '8px',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
    }}>
      <h2 style={{
        color: '#fafafa',
        fontSize: '20px',
        fontWeight: 600,
      }}>
        {title}
      </h2>
      <button style={{
        padding: '8px 16px',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: '#fff',
        border: 'none',
        borderRadius: '8px',
      }}>
        操作
      </button>
    </div>
  );
}
```

### After (新代码)

```tsx
// MyComponent.tsx
import styles from './MyComponent.module.css';

function MyComponent({ title }: Props) {
  return (
    <div className={styles.container}>
      <h2 className={styles.title}>{title}</h2>
      <button className={styles.button}>操作</button>
    </div>
  );
}
```

```css
/* MyComponent.module.css */
.container {
  padding: var(--spacing-4) var(--spacing-6);
  background-color: var(--color-neutral-900);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}

.title {
  color: var(--color-neutral-50);
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
}

.button {
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--color-primary-400);
  color: var(--color-white);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background-color 0.2s;
}

.button:hover {
  background: var(--color-primary-500);
}
```

---

**维护者**: Feagent Frontend Team
**联系**: 如有疑问或建议，请提交Issue
