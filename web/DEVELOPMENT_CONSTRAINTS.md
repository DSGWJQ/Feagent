# 🎨 Feagent 前端开发约束文档

> 本文档用于指导 AI 工具（如 v0.dev）生成符合项目规范的前端代码。
> **必须严格遵守本文档中的所有规范，不得偏离。**

---

## 📚 目录

1. [技术栈](#技术栈)
2. [项目结构](#项目结构)
3. [设计系统](#设计系统)
4. [代码规范](#代码规范)
5. [组件开发](#组件开发)
6. [样式规范](#样式规范)
7. [状态管理](#状态管理)
8. [API 调用](#api-调用)
9. [路由规范](#路由规范)
10. [类型定义](#类型定义)
11. [测试要求](#测试要求)
12. [命名约定](#命名约定)

---

## 🛠️ 技术栈

### 核心技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **React** | 18.3.1 | UI 框架 |
| **TypeScript** | 5.9.3 | 类型系统 |
| **Vite** | 7.2.2 | 构建工具 |
| **Ant Design** | 5.28.1 | UI 组件库 |
| **@xyflow/react** | 12.9.3 | Workflow 可视化 |
| **TanStack Query** | 5.90.9 | 数据获取与缓存 |
| **React Router DOM** | 7.9.6 | 路由管理 |
| **Axios** | 1.13.2 | HTTP 客户端 |

### 工具链

- **ESLint**: 代码检查
- **Prettier**: 代码格式化
- **Vitest**: 单元测试
- **Testing Library**: 组件测试

### 路径别名

```typescript
// vite.config.ts 已配置
'@' → 'src/'
'@/app' → 'src/app'
'@/layouts' → 'src/layouts'
'@/features' → 'src/features'
'@/shared' → 'src/shared'
'@/assets' → 'src/assets'
```

---

## 📁 项目结构

### 目录组织（严格遵守）

```
web/
├── src/
│   ├── app/                    # 应用层
│   │   ├── App.tsx            # 主应用组件
│   │   ├── router.tsx         # 路由配置
│   │   └── providers/         # Provider 组件
│   │       ├── QueryProvider.tsx
│   │       └── ...
│   │
│   ├── layouts/               # 布局组件
│   │   ├── MainLayout.tsx
│   │   └── ...
│   │
│   ├── features/              # 功能模块（按业务划分）
│   │   ├── agents/           # Agent 管理
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   ├── services/
│   │   │   ├── types/
│   │   │   └── pages/
│   │   ├── workflows/        # Workflow 管理
│   │   │   ├── components/
│   │   │   │   ├── nodes/   # Workflow 节点组件
│   │   │   │   └── ...
│   │   │   └── pages/
│   │   ├── tools/            # 工具管理
│   │   └── settings/         # 设置
│   │
│   ├── shared/               # 共享资源
│   │   ├── components/       # 通用组件
│   │   │   ├── common/      # 基础组件
│   │   │   ├── layout/      # 布局组件
│   │   │   └── neoclassical/ # 新古典主义装饰组件
│   │   ├── hooks/           # 通用 Hooks
│   │   ├── services/        # 通用服务
│   │   ├── contexts/        # Context（如 ThemeContext）
│   │   ├── utils/           # 工具函数
│   │   ├── types/           # 通用类型
│   │   └── styles/          # 样式系统
│   │       ├── tokens/      # 设计 Token
│   │       ├── global.css
│   │       ├── neoclassical.css
│   │       ├── theme.ts     # Ant Design 主题
│   │       └── themes.ts    # Dark/Light 主题
│   │
│   └── assets/              # 静态资源
│       ├── images/
│       ├── fonts/
│       └── icons/
│
├── public/                  # 公共资源
├── .env.example            # 环境变量示例
└── vite.config.ts          # Vite 配置
```

### 功能模块结构模板

每个 `features/` 下的功能模块应遵循以下结构：

```
features/[feature-name]/
├── components/          # 功能特定组件
│   ├── [Component].tsx
│   └── [Component].module.css
├── hooks/              # 功能特定 Hooks
│   └── use[Feature].ts
├── services/           # 功能特定服务（API 调用）
│   └── [feature]Api.ts
├── types/              # 功能特定类型
│   └── index.ts
└── pages/              # 功能页面
    └── [Feature]Page.tsx
```

---

## 🎨 设计系统

### 新古典主义设计理念

本项目采用**新古典主义（Neoclassical）设计系统**，灵感来自古希腊罗马建筑美学。

#### 核心原则

1. **黄金比例 (φ = 1.618)**：间距、字体缩放遵循黄金比例
2. **对称与平衡**：布局追求对称美学
3. **古典色彩**：金色、蓝色、灰度为主
4. **石雕质感**：使用纹理和阴影模拟大理石、花岗岩
5. **建筑元素**：柱式、拱门、浮雕装饰
6. **优雅动画**：缓慢、庄重的过渡效果

### 颜色系统（必须严格使用）

#### 核心调色板

| 颜色名称 | 值 | CSS 变量 | 用途 |
|---------|---|----------|------|
| 古典金 (Classical Gold) | `#D97706` | `var(--neo-gold)` | 主色、强调、装饰 |
| 皇家蓝 (Royal Blue) | `#1E40AF` | `var(--neo-blue)` | 链接、信息色 |
| 帝国红 (Imperial Red) | `#DC2626` | `var(--neo-red)` | 错误、危险色 |
| 深石墨 (Deep Graphite) | `#374151` | `var(--neo-text)` | 主文本（浅色主题） |
| 阴影灰 (Shadow Grey) | `#6B7280` | `var(--neo-text-2)` | 次要文本 |
| 大理石白 (Marble White) | `#FFFFFF` | `var(--neo-bg)` | 背景（浅色主题） |
| 优雅灰白 (Elegant Grey) | `#F9FAFB` | `var(--neo-surface)` | 表面色 |

#### 色阶系统

```typescript
// 导入方式
import { neoclassicalColors } from '@/shared/styles/tokens/neoclassicalColors';

// 使用示例
const color = neoclassicalColors.palette.classicalGold;       // 古典金
const bgColor = neoclassicalColors.scale.neutral[50];         // 灰度 50
const successColor = neoclassicalColors.semantic.success.main; // 语义色
```

#### 主题变量（支持 Dark/Light 切换）

**必须优先使用 CSS 变量，以支持主题切换：**

```css
/* 背景与表面 */
var(--neo-bg)         /* 主背景 */
var(--neo-surface)    /* 表面色 */
var(--neo-surface-2)  /* 次表面色 */

/* 文本 */
var(--neo-text)       /* 主文本 */
var(--neo-text-2)     /* 次要文本 */

/* 边框 */
var(--neo-border)     /* 边框色 */

/* 强调色 */
var(--neo-gold)       /* 古典金 */
var(--neo-blue)       /* 皇家蓝 */
var(--neo-red)        /* 帝国红 */

/* 焦点 */
var(--neo-focus)      /* 焦点色 */
```

#### 🚫 禁止使用的颜色

**以下旧颜色系统已废弃，严禁使用：**

```typescript
// ❌ 错误 - 旧蓝色系统
colors.primary[400]     // 不再使用
'#1a7fff'              // 不再使用
'#0066e6'              // 不再使用

// ❌ 错误 - 旧 CSS 变量
var(--color-primary-400)   // 不再使用
var(--color-secondary-500) // 不再使用

// ✅ 正确 - 新古典主义系统
neoclassicalColors.palette.classicalGold
var(--neo-gold)
```

### 间距系统（黄金比例）

```typescript
// 导入方式
import { space } from '@/shared/styles/tokens/space';

// Fibonacci 数列间距
space[0] // 0px
space[1] // 2px
space[2] // 3px
space[3] // 5px
space[4] // 8px
space[5] // 13px
space[6] // 21px
space[7] // 34px
space[8] // 55px
space[9] // 89px

// CSS 变量
var(--space-4)  // 8px
var(--space-6)  // 21px
```

### 字体系统

```typescript
// 导入方式
import { typography } from '@/shared/styles/tokens/typography';

// 字体族
typography.fontFamily.serif  // 新古典主义 Serif 字体
typography.fontFamily.base   // 系统默认字体
typography.fontFamily.code   // 代码字体

// 字体大小（黄金比例缩放）
typography.neoclassicalFontSize.xs    // 0.864rem
typography.neoclassicalFontSize.base  // 0.875rem (14px)
typography.neoclassicalFontSize.lg    // 1.113rem
typography.neoclassicalFontSize['2xl'] // 1.800rem

// 行高
typography.lineHeight.golden  // 1.618 (黄金比例)
typography.lineHeight.normal  // 1.5
```

### 装饰效果（neoclassical.css）

```tsx
// 石雕质感
<div className="neoStone">...</div>           // 通用石质效果
<div className="neoStoneMarble">...</div>     // 大理石效果
<div className="neoStoneGranite">...</div>    // 花岗岩效果

// 建筑阴影
<div className="neoShadowArch">...</div>      // 拱门阴影
<div className="neoShadowColumn">...</div>    // 柱式阴影
<div className="neoShadowRelief">...</div>    // 浮雕阴影

// 装饰边框
<div className="neoBorder">...</div>          // 基础边框
<div className="neoBorderDentil">...</div>    // 齿饰边框
<div className="neoRule">...</div>            // 装饰线

// 动画效果
<div className="neoEnterRadial">...</div>     // 径向进入
<div className="neoSymmetry">...</div>        // 对称展开
<div className="neoReveal">...</div>          // 揭幕效果
<div className="neoScaleIn">...</div>         // 缩放进入
```

### 装饰组件

```tsx
// 导入
import { Column } from '@/shared/components/neoclassical/Column';
import { Arch } from '@/shared/components/neoclassical/Arch';
import { ReliefPanel } from '@/shared/components/neoclassical/ReliefPanel';

// 柱式装饰（Doric, Ionic, Corinthian）
<Column order="doric" height={220} width={56} />

// 拱门结构
<Arch label="标题">
  <div>内容</div>
</Arch>

// 浮雕面板
<ReliefPanel title="面板标题">
  <div>内容</div>
</ReliefPanel>
```

---

## 📝 代码规范

### TypeScript 规范

#### 1. 严格模式（必须启用）

```typescript
// tsconfig.json 已配置
"strict": true,
"noImplicitAny": true,
"strictNullChecks": true
```

#### 2. 类型优先

```typescript
// ✅ 正确 - 显式类型
interface User {
  id: string;
  name: string;
  email: string;
}

const user: User = {
  id: '1',
  name: 'Alice',
  email: 'alice@example.com',
};

// ❌ 错误 - 隐式 any
const user = {
  id: '1',
  name: 'Alice',
};
```

#### 3. 类型导入

```typescript
// ✅ 正确 - 使用 import type
import type { User } from './types';
import { fetchUser } from './api';

// ❌ 错误 - 混合导入
import { User, fetchUser } from './api';
```

#### 4. 避免使用 `any`

```typescript
// ✅ 正确 - 使用具体类型或泛型
function processData<T>(data: T): T {
  return data;
}

// ❌ 错误 - 使用 any
function processData(data: any): any {
  return data;
}
```

### React 规范

#### 1. 函数组件（必须使用）

```tsx
// ✅ 正确 - 函数组件 + TypeScript
interface Props {
  title: string;
  count: number;
  onIncrement: () => void;
}

export function Counter({ title, count, onIncrement }: Props) {
  return (
    <div>
      <h2>{title}</h2>
      <p>Count: {count}</p>
      <button onClick={onIncrement}>+1</button>
    </div>
  );
}

// ❌ 错误 - 类组件（已废弃）
class Counter extends React.Component {
  // ...
}
```

#### 2. Hooks 规范

```tsx
// ✅ 正确 - 自定义 Hook 以 use 开头
function useCounter(initialValue: number = 0) {
  const [count, setCount] = useState(initialValue);

  const increment = useCallback(() => {
    setCount((prev) => prev + 1);
  }, []);

  return { count, increment };
}

// ❌ 错误 - 不以 use 开头
function getCounter() {
  const [count, setCount] = useState(0); // 违反 Hooks 规则
  return { count };
}
```

#### 3. Props 解构

```tsx
// ✅ 正确 - 解构 props
function Button({ label, onClick, disabled = false }: ButtonProps) {
  return <button onClick={onClick} disabled={disabled}>{label}</button>;
}

// ❌ 错误 - 不解构
function Button(props: ButtonProps) {
  return <button onClick={props.onClick}>{props.label}</button>;
}
```

#### 4. 条件渲染

```tsx
// ✅ 正确 - 使用 && 或三元运算符
{isLoading && <Spin />}
{error ? <Alert type="error" message={error} /> : <Content />}

// ❌ 错误 - 使用 if/else（在 JSX 中）
{if (isLoading) { return <Spin />; }}  // 语法错误
```

#### 5. 事件处理

```tsx
// ✅ 正确 - 使用箭头函数或 useCallback
function Form() {
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    // ...
  }, []);

  return <form onSubmit={handleSubmit}>...</form>;
}

// ❌ 错误 - 内联函数（性能问题）
<button onClick={() => console.log('clicked')}>Click</button>
```

### 代码风格

#### 1. 文件命名

```
Components: PascalCase.tsx           (Counter.tsx)
Hooks: camelCase.ts                  (useCounter.ts)
Utils: camelCase.ts                  (formatDate.ts)
Types: camelCase.ts or PascalCase.ts (types.ts, User.ts)
CSS Modules: [Name].module.css       (Button.module.css)
```

#### 2. 导入顺序

```typescript
// 1. React 相关
import React, { useState, useEffect } from 'react';
import type { FC } from 'react';

// 2. 第三方库
import { Button, Form } from 'antd';
import { useQuery } from '@tanstack/react-query';

// 3. 项目内部 - 绝对路径（使用别名）
import { useAuth } from '@/shared/hooks/useAuth';
import { formatDate } from '@/shared/utils/date';
import type { User } from '@/shared/types';

// 4. 相对路径
import { Header } from './Header';
import styles from './Layout.module.css';

// 5. 样式
import './styles.css';
```

#### 3. 组件结构顺序

```tsx
// 1. 导入
import ...

// 2. 类型定义
interface Props {
  ...
}

// 3. 常量
const DEFAULT_VALUE = 10;

// 4. 组件主体
export function Component({ prop1, prop2 }: Props) {
  // 4.1 Hooks
  const [state, setState] = useState();
  const query = useQuery(...);

  // 4.2 副作用
  useEffect(() => {
    ...
  }, []);

  // 4.3 事件处理函数
  const handleClick = useCallback(() => {
    ...
  }, []);

  // 4.4 渲染函数（如需要）
  const renderItem = (item: Item) => {
    ...
  };

  // 4.5 返回 JSX
  return (
    <div>...</div>
  );
}
```

---

## 🧩 组件开发

### Ant Design 组件（优先使用）

```tsx
// ✅ 正确 - 使用 Ant Design 组件
import { Button, Form, Input, Table, Modal, message } from 'antd';

function MyForm() {
  const [form] = Form.useForm();

  const handleSubmit = async (values: FormValues) => {
    try {
      await submitApi(values);
      message.success('提交成功');
    } catch (error) {
      message.error('提交失败');
    }
  };

  return (
    <Form form={form} onFinish={handleSubmit}>
      <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit">提交</Button>
      </Form.Item>
    </Form>
  );
}
```

### 自定义组件规范

#### 1. Props 接口

```typescript
// ✅ 正确 - 显式定义 Props
interface ButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
  className?: string;
}

export function Button({
  label,
  onClick,
  disabled = false,
  variant = 'primary',
  className
}: ButtonProps) {
  return (
    <button
      className={`${styles.button} ${styles[variant]} ${className || ''}`}
      onClick={onClick}
      disabled={disabled}
    >
      {label}
    </button>
  );
}
```

#### 2. 组件导出

```typescript
// ✅ 正确 - 命名导出（方便 tree-shaking）
export function Button(props: ButtonProps) { ... }

// ❌ 错误 - 默认导出（不推荐）
export default function Button(props: ButtonProps) { ... }
```

#### 3. 组件组合

```tsx
// ✅ 正确 - 使用组合而非继承
function Card({ title, children }: CardProps) {
  return (
    <div className={styles.card}>
      <div className={styles.header}>{title}</div>
      <div className={styles.body}>{children}</div>
    </div>
  );
}

function UserCard({ user }: UserCardProps) {
  return (
    <Card title={user.name}>
      <p>{user.email}</p>
    </Card>
  );
}
```

#### 4. Render Props Pattern

```tsx
// 用于需要高度自定义的场景
interface DataTableProps<T> {
  data: T[];
  renderRow: (item: T) => React.ReactNode;
}

function DataTable<T>({ data, renderRow }: DataTableProps<T>) {
  return (
    <div className={styles.table}>
      {data.map((item, index) => (
        <div key={index} className={styles.row}>
          {renderRow(item)}
        </div>
      ))}
    </div>
  );
}
```

---

## 🎨 样式规范

### CSS Modules（必须使用）

```tsx
// Button.tsx
import styles from './Button.module.css';

function Button({ variant = 'primary' }: ButtonProps) {
  return (
    <button className={`${styles.button} ${styles[variant]}`}>
      Click me
    </button>
  );
}
```

```css
/* Button.module.css */
.button {
  padding: var(--space-4) var(--space-6);
  border-radius: var(--radius-md);
  font-family: var(--font-family-serif);
  transition: all 0.3s ease;
}

.primary {
  background-color: var(--neo-gold);
  color: var(--neo-bg);
}

.primary:hover {
  filter: brightness(1.1);
}

.secondary {
  background-color: var(--neo-surface);
  color: var(--neo-text);
  border: 1px solid var(--neo-border);
}
```

### 样式规则

#### 1. 使用 CSS 变量

```css
/* ✅ 正确 - 使用 CSS 变量（支持主题切换） */
.card {
  background-color: var(--neo-bg);
  color: var(--neo-text);
  border: 1px solid var(--neo-border);
  border-radius: var(--radius-md);
  padding: var(--space-6);
}

/* ❌ 错误 - 硬编码颜色 */
.card {
  background-color: #ffffff;
  color: #374151;
  border: 1px solid #e5e7eb;
}
```

#### 2. 响应式设计

```css
/* Mobile First */
.container {
  padding: var(--space-4);
}

/* Tablet (≥ 768px) */
@media (min-width: 768px) {
  .container {
    padding: var(--space-6);
  }
}

/* Desktop (≥ 1024px) */
@media (min-width: 1024px) {
  .container {
    padding: var(--space-8);
  }
}
```

#### 3. 避免内联样式

```tsx
// ✅ 正确 - 使用 CSS Modules
<div className={styles.container}>...</div>

// ⚠️ 谨慎使用 - 仅用于动态值
<div style={{ width: `${progress}%` }}>...</div>

// ❌ 错误 - 硬编码内联样式
<div style={{ backgroundColor: '#1a7fff', padding: '16px' }}>...</div>
```

#### 4. 类名组合

```tsx
// ✅ 正确 - 使用模板字符串或 classnames 库
import classNames from 'classnames'; // 如果安装了

const buttonClass = classNames(
  styles.button,
  styles[variant],
  { [styles.disabled]: disabled },
  className
);

<button className={buttonClass}>...</button>

// 或者简单场景
<button className={`${styles.button} ${styles[variant]} ${className || ''}`}>
  ...
</button>
```

### Ant Design 主题定制

```typescript
// shared/styles/theme.ts
import type { ThemeConfig } from 'antd';
import { neoclassicalColors } from './tokens/neoclassicalColors';

export const theme: ThemeConfig = {
  token: {
    colorPrimary: neoclassicalColors.palette.classicalGold,
    colorSuccess: neoclassicalColors.semantic.success.main,
    colorWarning: neoclassicalColors.palette.classicalGold,
    colorError: neoclassicalColors.palette.imperialRed,
    colorInfo: neoclassicalColors.palette.royalBlue,

    fontFamily: typography.fontFamily.serif,
    borderRadius: parseInt(borderRadius.base),
    // ...
  },
  components: {
    Button: {
      primaryColor: neoclassicalColors.scale.neutral.white,
      primaryBg: neoclassicalColors.palette.classicalGold,
      // ...
    },
    // ...
  },
};
```

**不要在组件中覆盖 Ant Design 主题！** 所有主题定制应在 `theme.ts` 中完成。

---

## 🔄 状态管理

### TanStack Query（React Query）

#### 1. 数据获取

```typescript
// services/userApi.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
});

export const userApi = {
  getUsers: async (): Promise<User[]> => {
    const { data } = await apiClient.get('/users');
    return data;
  },

  getUser: async (id: string): Promise<User> => {
    const { data } = await apiClient.get(`/users/${id}`);
    return data;
  },

  createUser: async (user: CreateUserInput): Promise<User> => {
    const { data } = await apiClient.post('/users', user);
    return data;
  },
};
```

```tsx
// hooks/useUsers.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { userApi } from '../services/userApi';

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: userApi.getUsers,
  });
}

export function useUser(id: string) {
  return useQuery({
    queryKey: ['users', id],
    queryFn: () => userApi.getUser(id),
    enabled: !!id, // 仅当 id 存在时才执行
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: userApi.createUser,
    onSuccess: () => {
      // 使缓存失效，触发重新获取
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}
```

```tsx
// components/UserList.tsx
import { useUsers, useCreateUser } from '../hooks/useUsers';

function UserList() {
  const { data: users, isLoading, error } = useUsers();
  const createUser = useCreateUser();

  if (isLoading) return <Spin />;
  if (error) return <Alert type="error" message={error.message} />;

  const handleCreate = async () => {
    try {
      await createUser.mutateAsync({ name: 'New User', email: 'new@example.com' });
      message.success('创建成功');
    } catch (error) {
      message.error('创建失败');
    }
  };

  return (
    <div>
      <Button onClick={handleCreate}>创建用户</Button>
      {users?.map(user => (
        <div key={user.id}>{user.name}</div>
      ))}
    </div>
  );
}
```

#### 2. Query Keys 规范

```typescript
// ✅ 正确 - 使用数组和层级结构
['users']              // 所有用户
['users', userId]      // 单个用户
['users', userId, 'posts']  // 用户的文章

// 工厂函数（推荐）
export const userKeys = {
  all: ['users'] as const,
  lists: () => [...userKeys.all, 'list'] as const,
  list: (filters: string) => [...userKeys.lists(), { filters }] as const,
  details: () => [...userKeys.all, 'detail'] as const,
  detail: (id: string) => [...userKeys.details(), id] as const,
};

// 使用
useQuery({ queryKey: userKeys.detail(userId), ... });
```

### Context（全局状态）

```tsx
// contexts/ThemeContext.tsx
import { createContext, useContext, useState } from 'react';

interface ThemeContextValue {
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}
```

**使用场景**：
- ✅ 全局主题
- ✅ 用户认证状态
- ✅ 语言/国际化
- ❌ 服务端数据（使用 TanStack Query）
- ❌ 表单状态（使用本地 state）

---

## 🌐 API 调用

### Axios 配置

```typescript
// shared/services/apiClient.ts
import axios from 'axios';
import type { AxiosError } from 'axios';

export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 添加 token
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // 全局错误处理
    if (error.response?.status === 401) {
      // 跳转到登录页
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

### API Service 模式

```typescript
// features/agents/services/agentApi.ts
import { apiClient } from '@/shared/services/apiClient';
import type { Agent, CreateAgentInput, UpdateAgentInput } from '../types';

export const agentApi = {
  // 获取列表
  getAgents: async (): Promise<Agent[]> => {
    const { data } = await apiClient.get('/agents');
    return data;
  },

  // 获取单个
  getAgent: async (id: string): Promise<Agent> => {
    const { data } = await apiClient.get(`/agents/${id}`);
    return data;
  },

  // 创建
  createAgent: async (input: CreateAgentInput): Promise<Agent> => {
    const { data } = await apiClient.post('/agents', input);
    return data;
  },

  // 更新
  updateAgent: async (id: string, input: UpdateAgentInput): Promise<Agent> => {
    const { data } = await apiClient.put(`/agents/${id}`, input);
    return data;
  },

  // 删除
  deleteAgent: async (id: string): Promise<void> => {
    await apiClient.delete(`/agents/${id}`);
  },
};
```

### 错误处理

```typescript
// shared/utils/error.ts
import type { AxiosError } from 'axios';

export interface ApiError {
  message: string;
  code?: string;
  details?: Record<string, unknown>;
}

export function handleApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiError>;
    return {
      message: axiosError.response?.data?.message || '请求失败',
      code: axiosError.response?.data?.code,
      details: axiosError.response?.data?.details,
    };
  }

  if (error instanceof Error) {
    return { message: error.message };
  }

  return { message: '未知错误' };
}
```

```tsx
// 在组件中使用
import { handleApiError } from '@/shared/utils/error';

function MyComponent() {
  const createAgent = useCreateAgent();

  const handleSubmit = async (values: CreateAgentInput) => {
    try {
      await createAgent.mutateAsync(values);
      message.success('创建成功');
    } catch (error) {
      const apiError = handleApiError(error);
      message.error(apiError.message);
    }
  };

  return <Form onFinish={handleSubmit}>...</Form>;
}
```

---

## 🗺️ 路由规范

### React Router v7 配置

```typescript
// app/router.tsx
import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from '@/layouts/MainLayout';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'agents',
        children: [
          {
            index: true,
            element: <AgentListPage />,
          },
          {
            path: ':id',
            element: <AgentDetailPage />,
          },
          {
            path: 'new',
            element: <CreateAgentPage />,
          },
        ],
      },
      {
        path: 'workflows',
        children: [
          {
            index: true,
            element: <WorkflowListPage />,
          },
          {
            path: ':id/edit',
            element: <WorkflowEditorPage />,
          },
        ],
      },
    ],
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
]);
```

### 路由导航

```tsx
import { useNavigate, useParams, Link } from 'react-router-dom';

function MyComponent() {
  const navigate = useNavigate();
  const { id } = useParams();

  const handleClick = () => {
    navigate(`/agents/${id}/edit`);
  };

  return (
    <div>
      <Link to="/agents">返回列表</Link>
      <Button onClick={handleClick}>编辑</Button>
    </div>
  );
}
```

### 路径约定

```
/                    # 首页
/agents              # Agent 列表
/agents/:id          # Agent 详情
/agents/new          # 创建 Agent
/agents/:id/edit     # 编辑 Agent
/workflows           # Workflow 列表
/workflows/:id/edit  # Workflow 编辑器
/tools               # 工具列表
/settings            # 设置
/login               # 登录
```

---

## 📋 类型定义

### 实体类型

```typescript
// features/agents/types/index.ts

// 基础实体
export interface Agent {
  id: string;
  name: string;
  description: string;
  type: AgentType;
  status: AgentStatus;
  config: AgentConfig;
  createdAt: string;
  updatedAt: string;
}

// 枚举
export type AgentType = 'conversation' | 'workflow' | 'coordinator';
export type AgentStatus = 'active' | 'inactive' | 'error';

// 配置对象
export interface AgentConfig {
  model: string;
  temperature: number;
  maxTokens: number;
}

// 创建输入
export interface CreateAgentInput {
  name: string;
  description: string;
  type: AgentType;
  config: AgentConfig;
}

// 更新输入
export interface UpdateAgentInput {
  name?: string;
  description?: string;
  config?: Partial<AgentConfig>;
}
```

### DTO（Data Transfer Object）

```typescript
// API 请求/响应类型
export interface GetAgentsResponse {
  data: Agent[];
  total: number;
  page: number;
  pageSize: number;
}

export interface CreateAgentRequest {
  name: string;
  description: string;
  type: AgentType;
  config: AgentConfig;
}

export interface CreateAgentResponse {
  data: Agent;
  message: string;
}
```

### 组件 Props 类型

```typescript
// 组件 Props
export interface AgentCardProps {
  agent: Agent;
  onEdit?: (id: string) => void;
  onDelete?: (id: string) => void;
  className?: string;
}

// 泛型组件 Props
export interface DataTableProps<T> {
  data: T[];
  columns: ColumnConfig<T>[];
  loading?: boolean;
  onRowClick?: (item: T) => void;
}
```

### 工具类型

```typescript
// 使用 TypeScript 内置工具类型
type PartialAgent = Partial<Agent>;           // 所有属性可选
type RequiredAgent = Required<Agent>;         // 所有属性必填
type AgentKeys = keyof Agent;                 // 属性键联合类型
type AgentName = Pick<Agent, 'id' | 'name'>;  // 挑选部分属性
type AgentWithoutId = Omit<Agent, 'id'>;      // 排除部分属性
```

---

## 🧪 测试要求

### Vitest + Testing Library

```typescript
// components/Button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Button } from './Button';

describe('Button', () => {
  it('renders with label', () => {
    render(<Button label="Click me" onClick={() => {}} />);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const handleClick = vi.fn();
    render(<Button label="Click me" onClick={handleClick} />);

    fireEvent.click(screen.getByText('Click me'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button label="Click me" onClick={() => {}} disabled />);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

### 测试覆盖率要求

- 共享组件（`shared/components/`）：**≥ 80%**
- 功能模块组件（`features/*/components/`）：**≥ 60%**
- Hooks（`hooks/`）：**≥ 70%**
- Utils（`utils/`）：**≥ 80%**

### 运行测试

```bash
# 单次运行
pnpm test

# 监听模式
pnpm test:watch

# 生成覆盖率报告
pnpm test:coverage
```

---

## 🏷️ 命名约定

### 文件命名

| 类型 | 命名规则 | 示例 |
|------|---------|------|
| React 组件 | PascalCase.tsx | `Button.tsx`, `UserCard.tsx` |
| React Hooks | camelCase.ts (use前缀) | `useAuth.ts`, `useCounter.ts` |
| 工具函数 | camelCase.ts | `formatDate.ts`, `validateEmail.ts` |
| 类型文件 | camelCase.ts 或 PascalCase.ts | `types.ts`, `User.ts` |
| API 服务 | camelCase + Api.ts | `userApi.ts`, `agentApi.ts` |
| CSS Modules | [Name].module.css | `Button.module.css` |
| 常量文件 | camelCase.ts 或 UPPER_CASE.ts | `constants.ts`, `API_URLS.ts` |

### 变量命名

```typescript
// 常量 - UPPER_CASE
const MAX_RETRY_COUNT = 3;
const API_BASE_URL = '/api';

// 变量/函数 - camelCase
const userName = 'Alice';
const isActive = true;
function getUserById(id: string) { ... }

// 组件/类/接口 - PascalCase
interface User { ... }
class UserService { ... }
function Button() { ... }

// 类型别名 - PascalCase
type UserId = string;
type UserStatus = 'active' | 'inactive';

// 枚举 - PascalCase
enum AgentType {
  Conversation = 'conversation',
  Workflow = 'workflow',
}

// 私有变量 - _开头（不常用，TypeScript 中用 private）
const _internalCache = new Map();
```

### 事件处理函数

```typescript
// ✅ 正确 - handle前缀
const handleClick = () => { ... };
const handleSubmit = () => { ... };
const handleInputChange = () => { ... };

// ❌ 错误
const onClick = () => { ... };         // 与 prop 混淆
const submitForm = () => { ... };      // 不清晰
```

### Boolean 变量

```typescript
// ✅ 正确 - is/has/should/can 前缀
const isLoading = true;
const hasError = false;
const shouldRender = true;
const canEdit = false;

// ❌ 错误
const loading = true;   // 不清晰
const error = false;    // 混淆
```

---

## 🚀 开发工作流

### 1. 启动开发服务器

```bash
cd web
pnpm install
pnpm dev
```

访问: http://127.0.0.1:5173

### 2. 类型检查

```bash
pnpm type-check
```

### 3. 代码检查与格式化

```bash
# Lint
pnpm lint
pnpm lint:fix

# Format
pnpm format
pnpm format:check
```

### 4. 构建

```bash
pnpm build
```

### 5. 预览构建结果

```bash
pnpm preview
```

---

## ⚠️ 重要提醒

### 必须遵守的规则

1. **✅ 必须使用新古典主义颜色系统**，严禁使用旧颜色（`#1a7fff` 等）
2. **✅ 必须使用 CSS 变量**（`var(--neo-*)`），以支持主题切换
3. **✅ 必须使用 TypeScript 严格模式**，禁止 `any` 类型
4. **✅ 必须使用 CSS Modules**，避免全局样式污染
5. **✅ 必须使用 TanStack Query** 进行数据获取，不要在组件中直接调用 API
6. **✅ 必须使用 Ant Design 组件**，除非有特殊需求
7. **✅ 必须遵循文件组织结构**（features, shared, layouts）
8. **✅ 必须为组件编写类型定义**（Props interface）
9. **✅ 必须使用函数组件 + Hooks**，禁止类组件
10. **✅ 必须编写单元测试**（共享组件 ≥ 80% 覆盖率）

### 禁止的行为

1. **❌ 禁止使用旧的蓝色颜色系统** (`colors.primary`, `#1a7fff`)
2. **❌ 禁止硬编码颜色值**（除非是新古典主义调色板中的颜色）
3. **❌ 禁止在组件中使用 `any` 类型**
4. **❌ 禁止使用类组件**
5. **❌ 禁止直接在组件中调用 API**（使用 TanStack Query）
6. **❌ 禁止创建全局 CSS 类**（使用 CSS Modules）
7. **❌ 禁止在组件中覆盖 Ant Design 主题**（在 `theme.ts` 中统一配置）
8. **❌ 禁止使用默认导出**（使用命名导出）
9. **❌ 禁止混合导入类型和值**（使用 `import type`）
10. **❌ 禁止在 JSX 中使用内联函数**（影响性能，使用 `useCallback`）

---

## 📚 快速参考

### 颜色快速查找

| 场景 | 颜色 | CSS 变量 |
|------|------|----------|
| 主按钮背景 | 古典金 #D97706 | `var(--neo-gold)` |
| 链接颜色 | 皇家蓝 #1E40AF | `var(--neo-blue)` |
| 错误提示 | 帝国红 #DC2626 | `var(--neo-red)` |
| 页面背景 | 大理石白 #FFFFFF | `var(--neo-bg)` |
| 卡片背景 | 优雅灰白 #F9FAFB | `var(--neo-surface)` |
| 主文本 | 深石墨 #374151 | `var(--neo-text)` |
| 次要文本 | 阴影灰 #6B7280 | `var(--neo-text-2)` |
| 边框 | - | `var(--neo-border)` |

### 间距快速查找

| Token | 值 | 用途 |
|-------|---|------|
| `space[4]` / `var(--space-4)` | 8px | 小间距（按钮内边距） |
| `space[5]` / `var(--space-5)` | 13px | 中间距 |
| `space[6]` / `var(--space-6)` | 21px | 大间距（卡片内边距） |
| `space[7]` / `var(--space-7)` | 34px | 特大间距（模块间距） |

### 常用导入

```typescript
// 设计系统
import { neoclassicalColors } from '@/shared/styles/tokens/neoclassicalColors';
import { space } from '@/shared/styles/tokens/space';
import { typography } from '@/shared/styles/tokens/typography';

// 装饰组件
import { Column } from '@/shared/components/neoclassical/Column';
import { Arch } from '@/shared/components/neoclassical/Arch';
import { ReliefPanel } from '@/shared/components/neoclassical/ReliefPanel';

// Hooks
import { useTheme } from '@/shared/contexts/ThemeContext';
import { useQuery, useMutation } from '@tanstack/react-query';

// 路由
import { useNavigate, useParams, Link } from 'react-router-dom';

// Ant Design
import { Button, Form, Input, Table, Modal, message } from 'antd';
```

---

## 🎯 示例代码

### 完整的功能模块示例

```tsx
// features/agents/types/index.ts
export interface Agent {
  id: string;
  name: string;
  description: string;
  type: 'conversation' | 'workflow';
  status: 'active' | 'inactive';
  createdAt: string;
}

export interface CreateAgentInput {
  name: string;
  description: string;
  type: 'conversation' | 'workflow';
}
```

```typescript
// features/agents/services/agentApi.ts
import { apiClient } from '@/shared/services/apiClient';
import type { Agent, CreateAgentInput } from '../types';

export const agentApi = {
  getAgents: async (): Promise<Agent[]> => {
    const { data } = await apiClient.get('/agents');
    return data;
  },

  createAgent: async (input: CreateAgentInput): Promise<Agent> => {
    const { data } = await apiClient.post('/agents', input);
    return data;
  },
};
```

```typescript
// features/agents/hooks/useAgents.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '../services/agentApi';

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: agentApi.getAgents,
  });
}

export function useCreateAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: agentApi.createAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
}
```

```tsx
// features/agents/components/AgentCard.tsx
import type { Agent } from '../types';
import styles from './AgentCard.module.css';

interface AgentCardProps {
  agent: Agent;
  onEdit?: (id: string) => void;
}

export function AgentCard({ agent, onEdit }: AgentCardProps) {
  return (
    <div className={styles.card}>
      <h3 className={styles.title}>{agent.name}</h3>
      <p className={styles.description}>{agent.description}</p>
      <div className={styles.footer}>
        <span className={styles.type}>{agent.type}</span>
        {onEdit && (
          <button
            className={styles.editButton}
            onClick={() => onEdit(agent.id)}
          >
            编辑
          </button>
        )}
      </div>
    </div>
  );
}
```

```css
/* features/agents/components/AgentCard.module.css */
.card {
  background-color: var(--neo-surface);
  border: 1px solid var(--neo-border);
  border-radius: var(--radius-md);
  padding: var(--space-6);
  transition: all 0.3s ease;
}

.card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.title {
  font-family: var(--font-family-serif);
  font-size: var(--font-size-lg);
  color: var(--neo-text);
  margin-bottom: var(--space-3);
}

.description {
  color: var(--neo-text-2);
  line-height: 1.618;
  margin-bottom: var(--space-4);
}

.footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.type {
  font-size: var(--font-size-sm);
  color: var(--neo-gold);
  font-weight: 500;
}

.editButton {
  background-color: var(--neo-gold);
  color: var(--neo-bg);
  border: none;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-base);
  cursor: pointer;
  transition: filter 0.2s;
}

.editButton:hover {
  filter: brightness(1.1);
}
```

```tsx
// features/agents/pages/AgentListPage.tsx
import { Button, Spin, Alert, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useAgents, useCreateAgent } from '../hooks/useAgents';
import { AgentCard } from '../components/AgentCard';
import styles from './AgentListPage.module.css';

export function AgentListPage() {
  const navigate = useNavigate();
  const { data: agents, isLoading, error } = useAgents();
  const createAgent = useCreateAgent();

  if (isLoading) return <Spin size="large" />;
  if (error) return <Alert type="error" message="加载失败" />;

  const handleEdit = (id: string) => {
    navigate(`/agents/${id}/edit`);
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>Agent 管理</h1>
        <Button
          type="primary"
          onClick={() => navigate('/agents/new')}
        >
          创建 Agent
        </Button>
      </div>

      <div className={styles.grid}>
        {agents?.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            onEdit={handleEdit}
          />
        ))}
      </div>
    </div>
  );
}
```

---

## 📞 问题反馈

如果 AI 生成的代码不符合规范，请明确指出违反了哪条规则，并参考本文档进行修正。

**项目维护者**: Feagent Team
**文档版本**: 1.0.0
**最后更新**: 2025-12-14

---

**🎨 记住：优雅、简洁、类型安全、新古典主义美学！**
