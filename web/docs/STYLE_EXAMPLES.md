# 样式代码示例集

**Version**: 1.0.0
**Last Updated**: 2025-12-14

本文档提供常见UI模式的完整代码示例，可直接复制使用。

---

## 目录

1. [布局组件](#布局组件)
2. [表单组件](#表单组件)
3. [数据展示](#数据展示)
4. [反馈组件](#反馈组件)
5. [导航组件](#导航组件)
6. [动画效果](#动画效果)

---

## 布局组件

### 响应式容器

```tsx
// Container.tsx
import { ReactNode, memo } from 'react';
import styles from './Container.module.css';

interface ContainerProps {
  children: ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl';
}

function Container({ children, maxWidth = 'lg' }: ContainerProps) {
  return (
    <div className={`${styles.container} ${styles[`container${maxWidth.toUpperCase()}`]}`}>
      {children}
    </div>
  );
}

export default memo(Container);
```

```css
/* Container.module.css */
.container {
  width: 100%;
  margin-left: auto;
  margin-right: auto;
  padding-left: var(--spacing-4);
  padding-right: var(--spacing-4);
}

.containerSM {
  max-width: 640px;
}

.containerMD {
  max-width: 768px;
}

.containerLG {
  max-width: 1024px;
}

.containerXL {
  max-width: 1280px;
}

@media (min-width: 768px) {
  .container {
    padding-left: var(--spacing-6);
    padding-right: var(--spacing-6);
  }
}
```

---

### Grid布局

```tsx
// Grid.tsx
import { ReactNode, memo } from 'react';
import styles from './Grid.module.css';

interface GridProps {
  children: ReactNode;
  cols?: 1 | 2 | 3 | 4;
  gap?: number; // spacing token number
}

function Grid({ children, cols = 3, gap = 4 }: GridProps) {
  return (
    <div
      className={styles.grid}
      style={{
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: `var(--spacing-${gap})`,
      }}
    >
      {children}
    </div>
  );
}

export default memo(Grid);
```

```css
/* Grid.module.css */
.grid {
  display: grid;
}

@media (max-width: 768px) {
  .grid {
    grid-template-columns: 1fr !important;
  }
}
```

---

## 表单组件

### 输入框（带标签和错误）

```tsx
// Input.tsx
import { InputHTMLAttributes, memo } from 'react';
import styles from './Input.module.css';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

function Input({ label, error, helperText, className, ...props }: InputProps) {
  return (
    <div className={styles.inputWrapper}>
      {label && <label className={styles.label}>{label}</label>}
      <input
        className={`${styles.input} ${error ? styles.inputError : ''} ${className || ''}`}
        {...props}
      />
      {error && <p className={styles.error}>{error}</p>}
      {!error && helperText && <p className={styles.helperText}>{helperText}</p>}
    </div>
  );
}

export default memo(Input);
```

```css
/* Input.module.css */
.inputWrapper {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
}

.label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-neutral-50);
}

.input {
  padding: var(--spacing-2) var(--spacing-3);
  background-color: var(--color-neutral-900);
  border: 1px solid var(--color-neutral-700);
  border-radius: var(--radius-md);
  color: var(--color-neutral-50);
  font-size: var(--font-size-base);
  font-family: var(--font-family-base);
  transition: border-color 0.2s;
}

.input:focus {
  outline: none;
  border-color: var(--color-primary-400);
  box-shadow: 0 0 0 3px var(--color-overlay-20);
}

.input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.inputError {
  border-color: var(--color-error);
}

.inputError:focus {
  border-color: var(--color-error);
  box-shadow: 0 0 0 3px var(--color-error-bg);
}

.error {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--color-error);
}

.helperText {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--color-neutral-400);
}
```

---

### 开关（Switch）

```tsx
// Switch.tsx
import { memo } from 'react';
import styles from './Switch.module.css';

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
}

function Switch({ checked, onChange, label, disabled }: SwitchProps) {
  return (
    <label className={`${styles.switchWrapper} ${disabled ? styles.disabled : ''}`}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className={styles.switchInput}
      />
      <span className={`${styles.switch} ${checked ? styles.switchChecked : ''}`}>
        <span className={styles.switchThumb} />
      </span>
      {label && <span className={styles.label}>{label}</span>}
    </label>
  );
}

export default memo(Switch);
```

```css
/* Switch.module.css */
.switchWrapper {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  cursor: pointer;
}

.switchWrapper.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.switchInput {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.switch {
  position: relative;
  width: 44px;
  height: 24px;
  background-color: var(--color-neutral-700);
  border-radius: var(--radius-full);
  transition: background-color 0.2s;
}

.switchChecked {
  background-color: var(--color-primary-400);
}

.switchThumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background-color: var(--color-white);
  border-radius: var(--radius-full);
  transition: transform 0.2s;
  box-shadow: var(--shadow-sm);
}

.switchChecked .switchThumb {
  transform: translateX(20px);
}

.label {
  font-size: var(--font-size-base);
  color: var(--color-neutral-50);
}
```

---

## 数据展示

### Badge（徽章）

```tsx
// Badge.tsx
import { ReactNode, memo } from 'react';
import styles from './Badge.module.css';

interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'success' | 'error' | 'warning' | 'info';
  size?: 'sm' | 'md';
}

function Badge({ children, variant = 'default', size = 'md' }: BadgeProps) {
  return (
    <span
      className={`${styles.badge} ${styles[`badge${variant.charAt(0).toUpperCase() + variant.slice(1)}`]} ${styles[`badge${size.toUpperCase()}`]}`}
    >
      {children}
    </span>
  );
}

export default memo(Badge);
```

```css
/* Badge.module.css */
.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  font-weight: var(--font-weight-medium);
  line-height: 1;
}

.badgeSM {
  padding: var(--spacing-1) var(--spacing-2);
  font-size: var(--font-size-xs);
}

.badgeMD {
  padding: var(--spacing-2) var(--spacing-3);
  font-size: var(--font-size-sm);
}

.badgeDefault {
  background-color: var(--color-neutral-700);
  color: var(--color-neutral-50);
}

.badgeSuccess {
  background-color: var(--color-success);
  color: var(--color-white);
}

.badgeError {
  background-color: var(--color-error);
  color: var(--color-white);
}

.badgeWarning {
  background-color: var(--color-warning);
  color: var(--color-neutral-900);
}

.badgeInfo {
  background-color: var(--color-info);
  color: var(--color-white);
}
```

---

### 进度条

```tsx
// Progress.tsx
import { memo } from 'react';
import styles from './Progress.module.css';

interface ProgressProps {
  value: number; // 0-100
  label?: string;
  showPercentage?: boolean;
  variant?: 'default' | 'success' | 'error';
}

function Progress({ value, label, showPercentage = true, variant = 'default' }: ProgressProps) {
  const clampedValue = Math.min(100, Math.max(0, value));

  return (
    <div className={styles.progressWrapper}>
      {(label || showPercentage) && (
        <div className={styles.progressHeader}>
          {label && <span className={styles.label}>{label}</span>}
          {showPercentage && <span className={styles.percentage}>{clampedValue}%</span>}
        </div>
      )}
      <div className={styles.progressTrack}>
        <div
          className={`${styles.progressBar} ${styles[`progressBar${variant.charAt(0).toUpperCase() + variant.slice(1)}`]}`}
          style={{ width: `${clampedValue}%` }}
        />
      </div>
    </div>
  );
}

export default memo(Progress);
```

```css
/* Progress.module.css */
.progressWrapper {
  width: 100%;
}

.progressHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-2);
}

.label {
  font-size: var(--font-size-sm);
  color: var(--color-neutral-50);
}

.percentage {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-neutral-400);
}

.progressTrack {
  width: 100%;
  height: 8px;
  background-color: var(--color-neutral-800);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progressBar {
  height: 100%;
  transition: width 0.3s ease;
  border-radius: var(--radius-full);
}

.progressBarDefault {
  background-color: var(--color-primary-400);
}

.progressBarSuccess {
  background-color: var(--color-success);
}

.progressBarError {
  background-color: var(--color-error);
}
```

---

## 反馈组件

### Toast通知

```tsx
// Toast.tsx
import { memo, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import styles from './Toast.module.css';

interface ToastProps {
  message: string;
  type?: 'success' | 'error' | 'warning' | 'info';
  duration?: number; // ms
  onClose: () => void;
}

function Toast({ message, type = 'info', duration = 3000, onClose }: ToastProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // 淡入
    setTimeout(() => setIsVisible(true), 10);

    // 自动关闭
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(onClose, 300); // 等待淡出动画
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  return createPortal(
    <div
      className={`${styles.toast} ${styles[`toast${type.charAt(0).toUpperCase() + type.slice(1)}`]} ${isVisible ? styles.toastVisible : ''}`}
    >
      {message}
    </div>,
    document.body
  );
}

export default memo(Toast);
```

```css
/* Toast.module.css */
.toast {
  position: fixed;
  top: var(--spacing-4);
  right: var(--spacing-4);
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  font-size: var(--font-size-base);
  z-index: 9999;
  opacity: 0;
  transform: translateY(-10px);
  transition: opacity 0.3s, transform 0.3s;
}

.toastVisible {
  opacity: 1;
  transform: translateY(0);
}

.toastSuccess {
  background-color: var(--color-success);
  color: var(--color-white);
}

.toastError {
  background-color: var(--color-error);
  color: var(--color-white);
}

.toastWarning {
  background-color: var(--color-warning);
  color: var(--color-neutral-900);
}

.toastInfo {
  background-color: var(--color-info);
  color: var(--color-white);
}
```

---

### 加载骨架屏

```tsx
// Skeleton.tsx
import { memo } from 'react';
import styles from './Skeleton.module.css';

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  variant?: 'text' | 'circular' | 'rectangular';
}

function Skeleton({ width, height, variant = 'text' }: SkeletonProps) {
  const style = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
  };

  return (
    <div
      className={`${styles.skeleton} ${styles[`skeleton${variant.charAt(0).toUpperCase() + variant.slice(1)}`]}`}
      style={style}
    />
  );
}

export default memo(Skeleton);
```

```css
/* Skeleton.module.css */
.skeleton {
  background: linear-gradient(
    90deg,
    var(--color-neutral-800) 25%,
    var(--color-neutral-700) 50%,
    var(--color-neutral-800) 75%
  );
  background-size: 200% 100%;
  animation: loading 1.5s ease-in-out infinite;
}

@keyframes loading {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.skeletonText {
  height: 16px;
  border-radius: var(--radius-sm);
}

.skeletonCircular {
  border-radius: var(--radius-full);
}

.skeletonRectangular {
  border-radius: var(--radius-md);
}
```

---

## 导航组件

### Tabs（标签页）

```tsx
// Tabs.tsx
import { ReactNode, memo, useState } from 'react';
import styles from './Tabs.module.css';

interface Tab {
  key: string;
  label: string;
  content: ReactNode;
}

interface TabsProps {
  tabs: Tab[];
  defaultActiveKey?: string;
  onChange?: (key: string) => void;
}

function Tabs({ tabs, defaultActiveKey, onChange }: TabsProps) {
  const [activeKey, setActiveKey] = useState(defaultActiveKey || tabs[0]?.key);

  const handleTabClick = (key: string) => {
    setActiveKey(key);
    onChange?.(key);
  };

  const activeTab = tabs.find((tab) => tab.key === activeKey);

  return (
    <div className={styles.tabs}>
      <div className={styles.tabsHeader}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`${styles.tab} ${activeKey === tab.key ? styles.tabActive : ''}`}
            onClick={() => handleTabClick(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className={styles.tabsContent}>{activeTab?.content}</div>
    </div>
  );
}

export default memo(Tabs);
```

```css
/* Tabs.module.css */
.tabs {
  width: 100%;
}

.tabsHeader {
  display: flex;
  gap: var(--spacing-1);
  border-bottom: 1px solid var(--color-neutral-800);
}

.tab {
  padding: var(--spacing-3) var(--spacing-4);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--color-neutral-400);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all 0.2s;
}

.tab:hover {
  color: var(--color-neutral-50);
}

.tabActive {
  color: var(--color-primary-400);
  border-bottom-color: var(--color-primary-400);
}

.tabsContent {
  padding: var(--spacing-4) 0;
}
```

---

## 动画效果

### 淡入淡出

```css
/* fade.module.css */
.fade {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.fadeOut {
  animation: fadeOut 0.3s ease-out;
}

@keyframes fadeOut {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}
```

---

### 滑入滑出

```css
/* slide.module.css */
.slideInRight {
  animation: slideInRight 0.3s ease-out;
}

@keyframes slideInRight {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.slideInLeft {
  animation: slideInLeft 0.3s ease-out;
}

@keyframes slideInLeft {
  from {
    transform: translateX(-100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
```

---

### 脉冲动画

```css
/* pulse.module.css */
.pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.pulseRing {
  animation: pulseRing 1.5s ease-out infinite;
}

@keyframes pulseRing {
  0% {
    transform: scale(0.8);
    opacity: 1;
  }
  100% {
    transform: scale(2);
    opacity: 0;
  }
}
```

---

## 完整示例：登录表单

```tsx
// LoginForm.tsx
import { useState, FormEvent, memo } from 'react';
import styles from './LoginForm.module.css';

interface LoginFormProps {
  onSubmit: (email: string, password: string) => Promise<void>;
}

function LoginForm({ onSubmit }: LoginFormProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await onSubmit(email, password);
    } catch (err: any) {
      setError(err.message || '登录失败');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <h2 className={styles.title}>登录</h2>

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.field}>
        <label className={styles.label} htmlFor="email">
          邮箱
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={styles.input}
          required
        />
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="password">
          密码
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={styles.input}
          required
        />
      </div>

      <button type="submit" className={styles.submitButton} disabled={isLoading}>
        {isLoading ? '登录中...' : '登录'}
      </button>
    </form>
  );
}

export default memo(LoginForm);
```

```css
/* LoginForm.module.css */
.form {
  max-width: 400px;
  margin: 0 auto;
  padding: var(--spacing-8);
  background-color: var(--color-neutral-900);
  border: 1px solid var(--color-neutral-800);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}

.title {
  margin: 0 0 var(--spacing-6) 0;
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-neutral-50);
  text-align: center;
}

.error {
  padding: var(--spacing-3);
  margin-bottom: var(--spacing-4);
  background-color: var(--color-error-bg);
  color: var(--color-error);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
}

.field {
  margin-bottom: var(--spacing-4);
}

.label {
  display: block;
  margin-bottom: var(--spacing-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-neutral-50);
}

.input {
  width: 100%;
  padding: var(--spacing-3);
  background-color: var(--color-neutral-900);
  border: 1px solid var(--color-neutral-700);
  border-radius: var(--radius-md);
  color: var(--color-neutral-50);
  font-size: var(--font-size-base);
  font-family: var(--font-family-base);
  transition: border-color 0.2s;
}

.input:focus {
  outline: none;
  border-color: var(--color-primary-400);
  box-shadow: 0 0 0 3px var(--color-overlay-20);
}

.submitButton {
  width: 100%;
  padding: var(--spacing-3);
  background-color: var(--color-primary-400);
  color: var(--color-white);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
  transition: background-color 0.2s;
}

.submitButton:hover:not(:disabled) {
  background-color: var(--color-primary-500);
}

.submitButton:active:not(:disabled) {
  background-color: var(--color-primary-600);
}

.submitButton:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

---

**维护者**: Feagent Frontend Team
**联系**: 如有疑问或建议，请提交Issue
