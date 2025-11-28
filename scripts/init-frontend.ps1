# 前端项目初始化脚本（PowerShell）
# 用途：快速创建前端项目骨架和基础目录结构

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Agent 中台系统 - 前端项目初始化" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否在项目根目录
$currentPath = Get-Location
Write-Host "当前目录: $currentPath" -ForegroundColor Yellow

# 检查 pnpm 是否安装
Write-Host ""
Write-Host "检查 pnpm 是否安装..." -ForegroundColor Green
$pnpmVersion = pnpm --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: 未检测到 pnpm，请先安装 pnpm" -ForegroundColor Red
    Write-Host "安装命令: npm install -g pnpm" -ForegroundColor Yellow
    exit 1
}
Write-Host "pnpm 版本: $pnpmVersion" -ForegroundColor Green

# 检查 web 目录是否已存在
if (Test-Path "web") {
    Write-Host ""
    Write-Host "警告: web 目录已存在" -ForegroundColor Yellow
    $confirm = Read-Host "是否删除并重新创建? (y/N)"
    if ($confirm -eq "y" -or $confirm -eq "Y") {
        Write-Host "删除现有 web 目录..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force "web"
    } else {
        Write-Host "取消初始化" -ForegroundColor Red
        exit 0
    }
}

# 创建 Vite 项目
Write-Host ""
Write-Host "步骤 1/5: 创建 Vite + React + TypeScript 项目..." -ForegroundColor Green
pnpm create vite web --template react-ts
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: 创建项目失败" -ForegroundColor Red
    exit 1
}
Write-Host "项目创建成功" -ForegroundColor Green

# 进入项目目录
Set-Location "web"

# 安装基础依赖
Write-Host ""
Write-Host "步骤 2/5: 安装基础依赖..." -ForegroundColor Green
Write-Host "这可能需要几分钟时间，请耐心等待..." -ForegroundColor Yellow

# 安装核心依赖
pnpm add antd @ant-design/pro-components @ant-design/icons react-router-dom @tanstack/react-query axios

# 安装开发依赖
pnpm add -D @types/node eslint-config-prettier

Write-Host "依赖安装完成" -ForegroundColor Green

# 创建目录结构
Write-Host ""
Write-Host "步骤 3/5: 创建目录结构..." -ForegroundColor Green

$directories = @(
    "src/app/providers",
    "src/layouts/components",
    "src/features/agents/pages",
    "src/features/agents/components",
    "src/features/agents/hooks",
    "src/features/agents/types",
    "src/features/agents/api",
    "src/features/runs/pages",
    "src/features/runs/components",
    "src/features/runs/hooks",
    "src/features/runs/types",
    "src/features/runs/api",
    "src/features/settings/pages",
    "src/features/settings/components",
    "src/shared/components",
    "src/shared/hooks",
    "src/shared/utils",
    "src/shared/types",
    "src/shared/styles",
    "src/assets/images",
    "src/assets/icons"
)

foreach ($dir in $directories) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host "  创建目录: $dir" -ForegroundColor Gray
}

Write-Host "目录结构创建完成" -ForegroundColor Green

# 创建配置文件
Write-Host ""
Write-Host "步骤 4/5: 创建配置文件..." -ForegroundColor Green

# 创建 .env.development
@"
# API 基础 URL
VITE_API_BASE_URL=http://localhost:8000

# 应用标题
VITE_APP_TITLE=Agent 中台系统

# 是否启用 Mock
VITE_USE_MOCK=false
"@ | Out-File -FilePath ".env.development" -Encoding utf8
Write-Host "  创建 .env.development" -ForegroundColor Gray

# 创建 .env.production
@"
# API 基础 URL
VITE_API_BASE_URL=https://api.example.com

# 应用标题
VITE_APP_TITLE=Agent 中台系统

# 是否启用 Mock
VITE_USE_MOCK=false
"@ | Out-File -FilePath ".env.production" -Encoding utf8
Write-Host "  创建 .env.production" -ForegroundColor Gray

# 创建 .prettierrc
@"
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
"@ | Out-File -FilePath ".prettierrc" -Encoding utf8
Write-Host "  创建 .prettierrc" -ForegroundColor Gray

# 更新 vite.config.ts
@"
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
"@ | Out-File -FilePath "vite.config.ts" -Encoding utf8
Write-Host "  更新 vite.config.ts" -ForegroundColor Gray

# 更新 tsconfig.json（添加路径别名）
$tsconfigContent = @"
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
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
"@
$tsconfigContent | Out-File -FilePath "tsconfig.json" -Encoding utf8
Write-Host "  更新 tsconfig.json" -ForegroundColor Gray

Write-Host "配置文件创建完成" -ForegroundColor Green

# 创建基础文件
Write-Host ""
Write-Host "步骤 5/5: 创建基础文件..." -ForegroundColor Green

# 创建 API 类型定义
@"
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
"@ | Out-File -FilePath "src/shared/types/api.ts" -Encoding utf8
Write-Host "  创建 src/shared/types/api.ts" -ForegroundColor Gray

# 创建全局样式
@"
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
"@ | Out-File -FilePath "src/shared/styles/global.css" -Encoding utf8
Write-Host "  创建 src/shared/styles/global.css" -ForegroundColor Gray

# 创建主题配置
@"
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
"@ | Out-File -FilePath "src/shared/styles/theme.ts" -Encoding utf8
Write-Host "  创建 src/shared/styles/theme.ts" -ForegroundColor Gray

# 创建 README
@"
# Agent 中台系统 - 前端

基于 Vite + React + TypeScript + Ant Design Pro Components 构建的企业级 Agent 中台系统前端。

## 技术栈

- **构建工具**: Vite 5.x
- **框架**: React 18.x + TypeScript 5.x
- **UI 组件库**: Ant Design 5.x + Pro Components
- **路由**: React Router v6
- **状态管理**: TanStack Query v5
- **HTTP 客户端**: axios

## 开发

``````bash
# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev

# 构建生产版本
pnpm build

# 预览生产版本
pnpm preview
``````

## 目录结构

详见 ``docs/frontend_setup_guide.md``

## 文档

- [前端结构规范](.augment/rules/frontend_structure.md)
- [开发文档](docs/develop_document.md)
- [初始化指南](docs/frontend_setup_guide.md)
"@ | Out-File -FilePath "README.md" -Encoding utf8
Write-Host "  创建 README.md" -ForegroundColor Gray

Write-Host "基础文件创建完成" -ForegroundColor Green

# 返回项目根目录
Set-Location ..

# 完成
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  前端项目初始化完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步操作:" -ForegroundColor Yellow
Write-Host "  1. cd web" -ForegroundColor White
Write-Host "  2. pnpm dev" -ForegroundColor White
Write-Host ""
Write-Host "项目将运行在: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "详细文档请查看:" -ForegroundColor Yellow
Write-Host "  - docs/frontend_setup_guide.md" -ForegroundColor White
Write-Host "  - .augment/rules/frontend_structure.md" -ForegroundColor White
Write-Host ""
