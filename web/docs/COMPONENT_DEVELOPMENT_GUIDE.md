# 组件开发指南

**Version**: 1.0.0
**Last Updated**: 2025-12-14

---

## 目录

1. [快速开始](#快速开始)
2. [CSS Module使用](#css-module使用)
3. [设计Token使用](#设计token使用)
4. [组件开发流程](#组件开发流程)
5. [常见模式](#常见模式)
6. [性能优化](#性能优化)
7. [测试指南](#测试指南)
8. [常见问题](#常见问题)

---

## 快速开始

### 创建新组件

**1. 创建组件文件**

```tsx
// src/features/myFeature/components/MyComponent.tsx
import { memo } from 'react';
import styles from './MyComponent.module.css';

interface MyComponentProps {
  title: string;
  onAction?: () => void;
}

function MyComponent({ title, onAction }: MyComponentProps) {
  return (
    <div className={styles.container}>
      <h2 className={styles.title}>{title}</h2>
      <button className={styles.actionButton} onClick={onAction}>
        操作
      </button>
    </div>
  );
}

export default memo(MyComponent);
```

**2. 创建CSS Module**

```css
/* src/features/myFeature/components/MyComponent.module.css */
.container {
  padding: var(--spacing-4);
  background-color: var(--color-neutral-900);
  border: 1px solid var(--color-neutral-800);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}

.title {
  margin: 0 0 var(--spacing-3) 0;
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-neutral-50);
}

.actionButton {
  padding: var(--spacing-2) var(--spacing-4);
  background-color: var(--color-primary-400);
  color: var(--color-white);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  cursor: pointer;
  transition: background-color 0.2s;
}

.actionButton:hover {
  background-color: var(--color-primary-500);
}

.actionButton:active {
  background-color: var(--color-primary-600);
}
```

---

## CSS Module使用

### 基础用法

**导入样式**:
```tsx
import styles from './MyComponent.module.css';
```

**应用单个class**:
```tsx
<div className={styles.container}>
```

**应用多个classes**:
```tsx
<div className={`${styles.container} ${styles.highlighted}`}>
```

**条件class**:
```tsx
<div className={`${styles.card} ${isActive ? styles.active : ''}`}>
```

**模板字符串拼接**:
```tsx
<div
  className={`${styles.button} ${
    variant === 'primary' ? styles.buttonPrimary : styles.buttonSecondary
  }`}
>
```

---

### 全局样式选择器

在CSS Module中访问全局class（如Ant Design或ReactFlow）：

```css
/* 使用:global()选择器 */
.reactFlowWrapper :global(.react-flow__controls) {
  background: var(--color-neutral-900);
  border: 1px solid var(--color-neutral-800);
}

.reactFlowWrapper :global(.react-flow__controls button) {
  color: var(--color-neutral-50);
}

.reactFlowWrapper :global(.react-flow__controls button:hover) {
  background: var(--color-neutral-800);
}
```

**使用场景**:
- 覆盖第三方组件样式（Ant Design, ReactFlow）
- 与全局CSS交互
- 动画keyframes定义

---

### 组合与继承

**错误方式** ❌:
```css
/* CSS不支持直接继承 */
.buttonSecondary {
  @extend .buttonBase; /* ❌ CSS Module不支持 */
}
```

**正确方式** ✅:
```tsx
// 在JSX中组合多个class
<button className={`${styles.buttonBase} ${styles.buttonSecondary}`}>
```

或使用共享CSS变量：
```css
/* 定义共享样式变量 */
.buttonBase {
  padding: var(--spacing-2) var(--spacing-4);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  transition: all 0.2s;
}

.buttonPrimary {
  composes: buttonBase; /* CSS Modules的composes */
  background-color: var(--color-primary-400);
  color: var(--color-white);
}
```

---

## 设计Token使用

### 颜色

**推荐**:
```css
.card {
  background-color: var(--color-neutral-900);
  color: var(--color-neutral-50);
  border: 1px solid var(--color-neutral-800);
}
```

**带fallback（SVG/Canvas必须）**:
```css
.nodeCircle {
  fill: var(--color-primary-400, #1a7fff);
  stroke: var(--color-neutral-600, #4a4a4a);
}
```

**条件颜色**:
```tsx
// ✅ 使用CSS class切换
<div className={`${styles.status} ${isOnline ? styles.statusOnline : styles.statusOffline}`}>

// CSS
.status {
  padding: var(--spacing-1) var(--spacing-2);
  border-radius: var(--radius-full);
}

.statusOnline {
  background-color: var(--color-success);
  color: var(--color-white);
}

.statusOffline {
  background-color: var(--color-neutral-600);
  color: var(--color-neutral-300);
}
```

---

### 间距

**内边距**:
```css
.card {
  padding: var(--spacing-4); /* 16px 四周 */
  padding: var(--spacing-3) var(--spacing-4); /* 12px 16px */
}
```

**外边距**:
```css
.section {
  margin-bottom: var(--spacing-6); /* 24px */
}
```

**间隙（Flexbox/Grid）**:
```css
.buttonGroup {
  display: flex;
  gap: var(--spacing-2); /* 8px */
}
```

**4px网格对齐**:
```css
/* ✅ 推荐 - 使用spacing token */
margin-top: var(--spacing-3); /* 12px */

/* ❌ 避免 - 破坏网格 */
margin-top: 10px;
```

---

### 排版

**字体大小**:
```css
.pageTitle {
  font-size: var(--font-size-3xl); /* 30px */
}

.cardTitle {
  font-size: var(--font-size-xl); /* 20px */
}

.bodyText {
  font-size: var(--font-size-base); /* 16px */
}

.caption {
  font-size: var(--font-size-sm); /* 14px */
}
```

**字重**:
```css
.title {
  font-weight: var(--font-weight-semibold); /* 600 */
}

.bodyText {
  font-weight: var(--font-weight-normal); /* 400 */
}
```

**字体家族**:
```css
.bodyText {
  font-family: var(--font-family-base);
}

.codeBlock {
  font-family: var(--font-family-code);
}
```

---

### 阴影与圆角

**阴影**:
```css
.card {
  box-shadow: var(--shadow-md); /* 标准卡片 */
}

.modal {
  box-shadow: var(--shadow-lg); /* 模态框 */
}

.button:hover {
  box-shadow: var(--shadow-sm); /* 悬浮提示 */
}
```

**圆角**:
```css
.button {
  border-radius: var(--radius-md); /* 8px - 标准 */
}

.card {
  border-radius: var(--radius-lg); /* 12px - 大卡片 */
}

.avatar {
  border-radius: var(--radius-full); /* 圆形 */
}
```

---

## 组件开发流程

### 标准工作流

**1. 分析设计稿/需求**
- 识别需要的颜色、间距、字体
- 确定组件状态（hover, active, disabled）
- 确定响应式需求

**2. 创建组件骨架**
```tsx
// MyComponent.tsx
import { memo } from 'react';
import styles from './MyComponent.module.css';

interface MyComponentProps {
  // Props定义
}

function MyComponent(props: MyComponentProps) {
  // 组件逻辑
  return (
    <div className={styles.container}>
      {/* JSX */}
    </div>
  );
}

export default memo(MyComponent);
```

**3. 创建CSS Module**
```css
/* MyComponent.module.css */
.container {
  /* 使用design tokens */
}
```

**4. 实现交互状态**
- Hover效果
- Active效果
- Disabled状态
- Loading状态

**5. 添加响应式**（如需要）
```css
@media (max-width: 768px) {
  .container {
    padding: var(--spacing-2);
  }
}
```

**6. 性能优化**
- 使用`memo`包裹组件
- 使用`useCallback`, `useMemo`优化回调

**7. 编写测试**
- 单元测试（行为测试）
- 快照测试（可选）

---

## 常见模式

### 模式1：卡片组件

```tsx
// Card.tsx
import { ReactNode, memo } from 'react';
import styles from './Card.module.css';

interface CardProps {
  title?: string;
  children: ReactNode;
  variant?: 'default' | 'highlighted';
  onClick?: () => void;
}

function Card({ title, children, variant = 'default', onClick }: CardProps) {
  return (
    <div
      className={`${styles.card} ${
        variant === 'highlighted' ? styles.cardHighlighted : ''
      }`}
      onClick={onClick}
    >
      {title && <h3 className={styles.cardTitle}>{title}</h3>}
      <div className={styles.cardContent}>{children}</div>
    </div>
  );
}

export default memo(Card);
```

```css
/* Card.module.css */
.card {
  padding: var(--spacing-4);
  background-color: var(--color-neutral-900);
  border: 1px solid var(--color-neutral-800);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  transition: all 0.2s;
}

.card:hover {
  border-color: var(--color-neutral-700);
  box-shadow: var(--shadow-lg);
}

.cardHighlighted {
  border-color: var(--color-primary-400);
}

.cardTitle {
  margin: 0 0 var(--spacing-3) 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-neutral-50);
}

.cardContent {
  color: var(--color-neutral-400);
  font-size: var(--font-size-base);
  line-height: var(--line-height-normal);
}
```

---

### 模式2：按钮组件

```tsx
// Button.tsx
import { ButtonHTMLAttributes, memo } from 'react';
import styles from './Button.module.css';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  className,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`${styles.button} ${styles[`button${variant.charAt(0).toUpperCase() + variant.slice(1)}`]} ${styles[`button${size.toUpperCase()}`]} ${className || ''}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? 'Loading...' : children}
    </button>
  );
}

export default memo(Button);
```

```css
/* Button.module.css */
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-md);
  font-family: var(--font-family-base);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all 0.2s;
}

.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Variants */
.buttonPrimary {
  background-color: var(--color-primary-400);
  color: var(--color-white);
}

.buttonPrimary:hover:not(:disabled) {
  background-color: var(--color-primary-500);
}

.buttonPrimary:active:not(:disabled) {
  background-color: var(--color-primary-600);
}

.buttonSecondary {
  background-color: var(--color-neutral-800);
  color: var(--color-neutral-50);
  border: 1px solid var(--color-neutral-700);
}

.buttonSecondary:hover:not(:disabled) {
  background-color: var(--color-neutral-700);
}

.buttonDanger {
  background-color: var(--color-error);
  color: var(--color-white);
}

.buttonDanger:hover:not(:disabled) {
  background-color: var(--color-error-dark);
}

/* Sizes */
.buttonSM {
  padding: var(--spacing-1) var(--spacing-2);
  font-size: var(--font-size-sm);
}

.buttonMD {
  padding: var(--spacing-2) var(--spacing-4);
  font-size: var(--font-size-base);
}

.buttonLG {
  padding: var(--spacing-3) var(--spacing-6);
  font-size: var(--font-size-lg);
}
```

---

### 模式3：列表组件

```tsx
// ListItem.tsx
import { ReactNode, memo } from 'react';
import styles from './ListItem.module.css';

interface ListItemProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  onClick?: () => void;
}

function ListItem({ icon, title, description, action, onClick }: ListItemProps) {
  return (
    <div className={styles.listItem} onClick={onClick}>
      {icon && <div className={styles.listItemIcon}>{icon}</div>}
      <div className={styles.listItemContent}>
        <h4 className={styles.listItemTitle}>{title}</h4>
        {description && <p className={styles.listItemDescription}>{description}</p>}
      </div>
      {action && <div className={styles.listItemAction}>{action}</div>}
    </div>
  );
}

export default memo(ListItem);
```

```css
/* ListItem.module.css */
.listItem {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--color-neutral-800);
  cursor: pointer;
  transition: background-color 0.2s;
}

.listItem:hover {
  background-color: var(--color-neutral-800);
}

.listItemIcon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--color-neutral-800);
  border-radius: var(--radius-md);
  color: var(--color-primary-400);
}

.listItemContent {
  flex: 1;
  min-width: 0; /* 允许文字截断 */
}

.listItemTitle {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--color-neutral-50);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.listItemDescription {
  margin: var(--spacing-1) 0 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-neutral-400);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.listItemAction {
  flex-shrink: 0;
}
```

---

## 性能优化

### 1. 使用React.memo

**何时使用**:
- 组件props变化频率低
- 组件渲染开销大
- 组件在列表中重复使用

```tsx
import { memo } from 'react';

function MyComponent(props) {
  // ...
}

export default memo(MyComponent);

// 自定义比较函数
export default memo(MyComponent, (prevProps, nextProps) => {
  // 返回true表示props未变化，跳过重渲染
  return prevProps.id === nextProps.id;
});
```

---

### 2. 使用useCallback和useMemo

```tsx
import { useCallback, useMemo } from 'react';

function ParentComponent() {
  // ✅ 缓存回调
  const handleClick = useCallback(() => {
    console.log('Clicked');
  }, []);

  // ✅ 缓存计算结果
  const expensiveValue = useMemo(() => {
    return computeExpensiveValue(data);
  }, [data]);

  return <ChildComponent onClick={handleClick} value={expensiveValue} />;
}
```

---

### 3. 避免inline对象/函数

```tsx
// ❌ 每次渲染都创建新对象，导致子组件重渲染
<MyComponent style={{ color: 'red' }} onClick={() => handleClick()} />

// ✅ 使用CSS class + 缓存回调
<MyComponent className={styles.redText} onClick={handleClick} />
```

---

### 4. 条件渲染优化

```tsx
// ✅ 使用条件渲染，避免不必要的DOM
{isVisible && <ExpensiveComponent />}

// ❌ 使用CSS隐藏，DOM仍存在
<ExpensiveComponent style={{ display: isVisible ? 'block' : 'none' }} />
```

---

## 测试指南

### 单元测试示例

```tsx
// MyComponent.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import MyComponent from './MyComponent';

describe('MyComponent', () => {
  it('renders title correctly', () => {
    render(<MyComponent title="Test Title" />);
    expect(screen.getByText('Test Title')).toBeInTheDocument();
  });

  it('calls onAction when button is clicked', () => {
    const handleAction = jest.fn();
    render(<MyComponent title="Test" onAction={handleAction} />);

    const button = screen.getByRole('button');
    fireEvent.click(button);

    expect(handleAction).toHaveBeenCalledTimes(1);
  });

  it('applies correct CSS class', () => {
    const { container } = render(<MyComponent title="Test" />);
    const element = container.firstChild;
    expect(element).toHaveClass('container'); // CSS Module生成的hash class
  });
});
```

---

## 常见问题

### Q1: CSS Module class名没有生效？

**原因**: CSS Module文件命名不正确

**解决**:
- 文件必须以 `.module.css` 结尾
- 导入时使用 `import styles from './xxx.module.css'`
- 应用时使用 `className={styles.xxx}`

---

### Q2: 如何覆盖Ant Design组件样式？

**方案1 - 使用CSS Module + :global()**:
```css
.myButton :global(.ant-btn) {
  background-color: var(--color-primary-400);
}
```

**方案2 - 使用inline style**:
```tsx
<Button
  style={{
    backgroundColor: 'var(--color-primary-400)',
  }}
>
```

**方案3 - 使用className + `!important`**:
```css
.myButton {
  background-color: var(--color-primary-400) !important;
}
```

---

### Q3: CSS Variables在旧浏览器不生效？

**解决**: 添加fallback值

```css
/* ✅ 带fallback */
color: var(--color-primary-400, #1a7fff);

/* ❌ 无fallback */
color: var(--color-primary-400);
```

**SVG中必须使用fallback**:
```tsx
<circle fill="var(--color-primary-400, #1a7fff)" />
```

---

### Q4: 间距应该用px还是rem？

**推荐**: 使用spacing tokens（px）

```css
/* ✅ 使用token */
padding: var(--spacing-4); /* 16px */

/* ✅ 字体大小使用rem */
font-size: var(--font-size-base); /* 1rem = 16px */
```

**原因**:
- Spacing使用px确保pixel-perfect对齐
- Font size使用rem支持用户浏览器字体大小设置

---

### Q5: 如何实现dark/light主题切换？

**当前实现**: 仅支持dark theme

**未来扩展**: 可通过动态修改CSS Variables实现

```typescript
// 未来实现参考
function switchTheme(theme: 'light' | 'dark') {
  const root = document.documentElement;

  if (theme === 'light') {
    root.style.setProperty('--color-neutral-900', '#ffffff');
    root.style.setProperty('--color-neutral-50', '#0a0a0a');
    // ... 更多变量
  } else {
    root.style.setProperty('--color-neutral-900', '#0a0a0a');
    root.style.setProperty('--color-neutral-50', '#fafafa');
  }
}
```

---

## 相关文档

- [设计系统文档](./DESIGN_SYSTEM.md)
- [样式迁移Checklist](./STYLE_MIGRATION_CHECKLIST.md)
- [代码示例集](./STYLE_EXAMPLES.md)

---

**维护者**: Feagent Frontend Team
**联系**: 如有疑问或建议，请提交Issue
