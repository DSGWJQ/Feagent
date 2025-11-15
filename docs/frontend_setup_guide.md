# 前端项目初始化指南

本文档提供前端项目的完整初始化步骤和配置文件示例。

## 1. 项目初始化

### 1.1 使用 Vite 创建项目

```bash
# 进入项目根目录
cd d:\My_Project\agent_data

# 使用 Vite 官方模板创建 React + TypeScript 项目
npm create vite@latest web -- --template react-ts

# 或使用 pnpm（推荐）
pnpm create vite web --template react-ts

# 进入项目目录
cd web

# 安装依赖
pnpm install
```

### 1.2 安装核心依赖

```bash
# Ant Design 和 Pro Components
pnpm add antd @ant-design/pro-components @ant-design/icons

# 路由
pnpm add react-router-dom

# 数据管理
pnpm add @tanstack/react-query

# HTTP 客户端
pnpm add axios

# 开发依赖
pnpm add -D @types/node
```

### 1.3 安装开发工具

```bash
# ESLint 和 Prettier
pnpm add -D eslint prettier eslint-config-prettier eslint-plugin-react eslint-plugin-react-hooks

# Git Hooks
pnpm add -D husky lint-staged

# 测试工具（可选）
pnpm add -D vitest @testing-library/react @testing-library/jest-dom
```

## 2. 配置文件

### 2.1 Vite 配置 (`vite.config.ts`)

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/app': path.resolve(__dirname, './src/app'),
      '@/layouts': path.resolve(__dirname, './src/layouts'),
      '@/features': path.resolve(__dirname, './src/features'),
      '@/shared': path.resolve(__dirname, './src/shared'),
      '@/assets': path.resolve(__dirname, './src/assets'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
```

### 2.2 TypeScript 配置 (`tsconfig.json`)

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",

    /* Linting */
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,

    /* Path Mapping */
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@/app/*": ["./src/app/*"],
      "@/layouts/*": ["./src/layouts/*"],
      "@/features/*": ["./src/features/*"],
      "@/shared/*": ["./src/shared/*"],
      "@/assets/*": ["./src/assets/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

### 2.3 ESLint 配置 (`.eslintrc.cjs`)

```javascript
module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
    'plugin:react/recommended',
    'prettier',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh', 'react', 'react-hooks'],
  rules: {
    'react-refresh/only-export-components': [
      'warn',
      { allowConstantExport: true },
    ],
    'react/react-in-jsx-scope': 'off',
    '@typescript-eslint/no-explicit-any': 'warn',
  },
  settings: {
    react: {
      version: 'detect',
    },
  },
};
```

### 2.4 Prettier 配置 (`.prettierrc`)

```json
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": true,
  "printWidth": 100,
  "tabWidth": 2,
  "useTabs": false,
  "arrowParens": "always",
  "endOfLine": "lf"
}
```

### 2.5 环境变量配置

**`.env.development`**:
```bash
# API 基础 URL
VITE_API_BASE_URL=http://localhost:8000

# 应用标题
VITE_APP_TITLE=Agent 中台系统

# 是否启用 Mock
VITE_USE_MOCK=false
```

**`.env.production`**:
```bash
# API 基础 URL
VITE_API_BASE_URL=https://api.example.com

# 应用标题
VITE_APP_TITLE=Agent 中台系统

# 是否启用 Mock
VITE_USE_MOCK=false
```

### 2.6 Package.json 脚本

```json
{
  "name": "agent-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "lint:fix": "eslint . --ext ts,tsx --fix",
    "format": "prettier --write \"src/**/*.{ts,tsx,css,json}\"",
    "type-check": "tsc --noEmit",
    "test": "vitest",
    "prepare": "husky install"
  },
  "dependencies": {
    "@ant-design/icons": "^5.2.6",
    "@ant-design/pro-components": "^2.6.43",
    "@tanstack/react-query": "^5.17.19",
    "antd": "^5.12.8",
    "axios": "^1.6.5",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.3"
  },
  "devDependencies": {
    "@types/node": "^20.11.5",
    "@types/react": "^18.2.48",
    "@types/react-dom": "^18.2.18",
    "@typescript-eslint/eslint-plugin": "^6.19.0",
    "@typescript-eslint/parser": "^6.19.0",
    "@vitejs/plugin-react": "^4.2.1",
    "eslint": "^8.56.0",
    "eslint-config-prettier": "^9.1.0",
    "eslint-plugin-react": "^7.33.2",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.5",
    "husky": "^8.0.3",
    "lint-staged": "^15.2.0",
    "prettier": "^3.2.4",
    "typescript": "^5.3.3",
    "vite": "^5.0.11"
  }
}
```

### 2.7 Git Hooks 配置

**`.husky/pre-commit`**:
```bash
#!/usr/bin/env sh
. "$(dirname -- "$0")/_/husky.sh"

npx lint-staged
```

**`lint-staged` 配置（在 package.json 中）**:
```json
{
  "lint-staged": {
    "*.{ts,tsx}": [
      "eslint --fix",
      "prettier --write"
    ],
    "*.{css,json,md}": [
      "prettier --write"
    ]
  }
}
```

## 3. 创建基础目录结构

```bash
# 在 web/src 目录下创建基础目录结构
cd web/src

# 创建目录
mkdir -p app/providers
mkdir -p layouts/components
mkdir -p features/agents/{pages,components,hooks,types,api}
mkdir -p features/runs/{pages,components,hooks,types,api}
mkdir -p features/settings/{pages,components}
mkdir -p shared/{components,hooks,utils,types,styles}
mkdir -p assets/{images,icons}
```

## 4. 核心文件示例

### 4.1 应用入口 (`src/app/main.tsx`)

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import '@/shared/styles/global.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

### 4.2 根组件 (`src/app/App.tsx`)

```typescript
import { RouterProvider } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import QueryProvider from './providers/QueryProvider';
import router from './router';
import { theme } from '@/shared/styles/theme';

function App() {
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <QueryProvider>
        <RouterProvider router={router} />
      </QueryProvider>
    </ConfigProvider>
  );
}

export default App;
```

### 4.3 TanStack Query Provider (`src/app/providers/QueryProvider.tsx`)

```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 分钟
    },
  },
});

export default function QueryProvider({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
```

### 4.4 主题配置 (`src/shared/styles/theme.ts`)

```typescript
import type { ThemeConfig } from 'antd';

export const theme: ThemeConfig = {
  token: {
    colorPrimary: '#1890ff',
    borderRadius: 4,
  },
  components: {
    Layout: {
      headerBg: '#001529',
      siderBg: '#001529',
    },
  },
};
```

### 4.5 全局样式 (`src/shared/styles/global.css`)

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body,
#root {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    sans-serif;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}
```

### 4.6 HTTP 客户端 (`src/shared/utils/request.ts`)

```typescript
import axios from 'axios';
import { message } from 'antd';
import type { Result } from '@/shared/types/api';

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
});

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    const result: Result = response.data;
    
    // 统一处理业务错误码
    if (result.code !== 2000) {
      message.error(result.message || '请求失败');
      return Promise.reject(new Error(result.message));
    }
    
    return result.data;
  },
  (error) => {
    // 网络错误处理
    if (error.response) {
      const status = error.response.status;
      switch (status) {
        case 401:
          message.error('未授权，请重新登录');
          // 跳转到登录页
          break;
        case 403:
          message.error('拒绝访问');
          break;
        case 404:
          message.error('请求的资源不存在');
          break;
        case 500:
          message.error('服务器错误');
          break;
        default:
          message.error(error.response.data?.message || '请求失败');
      }
    } else {
      message.error('网络错误，请检查网络连接');
    }
    
    return Promise.reject(error);
  }
);

export default request;
```

### 4.7 API 类型定义 (`src/shared/types/api.ts`)

```typescript
/**
 * 统一响应结构
 */
export interface Result<T = any> {
  code: number;
  message: string;
  data?: T;
  detail?: string;
  trace_id?: string;
}

/**
 * 分页结果
 */
export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * 分页查询参数
 */
export interface PageParams {
  page?: number;
  page_size?: number;
  [key: string]: any;
}
```

## 5. 启动项目

```bash
# 开发模式
pnpm dev

# 构建生产版本
pnpm build

# 预览生产版本
pnpm preview

# 代码检查
pnpm lint

# 代码格式化
pnpm format

# 类型检查
pnpm type-check
```

## 6. 下一步

1. **创建布局组件**: 实现 `BasicLayout` 和 `BlankLayout`
2. **配置路由**: 完善 `src/app/router.tsx`
3. **实现 Agent 模块**: 创建 Agent 相关页面和组件
4. **实现 Run 模块**: 创建 Run 相关页面和组件
5. **集成 SSE**: 实现实时日志查看功能

## 7. 常见问题

### 7.1 路径别名不生效

确保 `vite.config.ts` 和 `tsconfig.json` 中的路径配置一致。

### 7.2 Ant Design 样式不生效

确保在入口文件中导入了 Ant Design 的样式（Pro Components 会自动导入）。

### 7.3 开发环境 API 跨域问题

在 `vite.config.ts` 中配置了代理，确保后端服务运行在 `http://localhost:8000`。

## 8. 参考资源

- [Vite 官方文档](https://vitejs.dev/)
- [React 官方文档](https://react.dev/)
- [Ant Design 官方文档](https://ant.design/)
- [Ant Design Pro Components](https://procomponents.ant.design/)
- [TanStack Query 文档](https://tanstack.com/query/latest)
- [React Router 文档](https://reactrouter.com/)

