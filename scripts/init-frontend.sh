#!/bin/bash
# 前端项目初始化脚本（Bash）
# 用途：快速创建前端项目骨架和基础目录结构

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Agent 中台系统 - 前端项目初始化${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 检查是否在项目根目录
echo -e "${YELLOW}当前目录: $(pwd)${NC}"

# 检查 pnpm 是否安装
echo ""
echo -e "${GREEN}检查 pnpm 是否安装...${NC}"
if ! command -v pnpm &> /dev/null; then
    echo -e "${RED}错误: 未检测到 pnpm，请先安装 pnpm${NC}"
    echo -e "${YELLOW}安装命令: npm install -g pnpm${NC}"
    exit 1
fi
PNPM_VERSION=$(pnpm --version)
echo -e "${GREEN}✓ pnpm 版本: $PNPM_VERSION${NC}"

# 检查 web 目录是否已存在
if [ -d "web" ]; then
    echo ""
    echo -e "${YELLOW}警告: web 目录已存在${NC}"
    read -p "是否删除并重新创建? (y/N): " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        echo -e "${YELLOW}删除现有 web 目录...${NC}"
        rm -rf web
    else
        echo -e "${RED}取消初始化${NC}"
        exit 0
    fi
fi

# 创建 Vite 项目
echo ""
echo -e "${GREEN}步骤 1/5: 创建 Vite + React + TypeScript 项目...${NC}"
pnpm create vite web --template react-ts
echo -e "${GREEN}✓ 项目创建成功${NC}"

# 进入项目目录
cd web

# 安装基础依赖
echo ""
echo -e "${GREEN}步骤 2/5: 安装基础依赖...${NC}"
echo -e "${YELLOW}这可能需要几分钟时间，请耐心等待...${NC}"

# 安装核心依赖
pnpm add antd @ant-design/pro-components @ant-design/icons react-router-dom @tanstack/react-query axios

# 安装开发依赖
pnpm add -D @types/node eslint-config-prettier

echo -e "${GREEN}✓ 依赖安装完成${NC}"

# 创建目录结构
echo ""
echo -e "${GREEN}步骤 3/5: 创建目录结构...${NC}"

directories=(
    "src/app/providers"
    "src/layouts/components"
    "src/features/agents/pages"
    "src/features/agents/components"
    "src/features/agents/hooks"
    "src/features/agents/types"
    "src/features/agents/api"
    "src/features/runs/pages"
    "src/features/runs/components"
    "src/features/runs/hooks"
    "src/features/runs/types"
    "src/features/runs/api"
    "src/features/settings/pages"
    "src/features/settings/components"
    "src/shared/components"
    "src/shared/hooks"
    "src/shared/utils"
    "src/shared/types"
    "src/shared/styles"
    "src/assets/images"
    "src/assets/icons"
)

for dir in "${directories[@]}"; do
    mkdir -p "$dir"
    echo -e "${GRAY}  ✓ 创建目录: $dir${NC}"
done

echo -e "${GREEN}✓ 目录结构创建完成${NC}"

# 创建配置文件
echo ""
echo -e "${GREEN}步骤 4/5: 创建配置文件...${NC}"

# 创建 .env.development
cat > .env.development << 'EOF'
# API 基础 URL
VITE_API_BASE_URL=http://localhost:8000

# 应用标题
VITE_APP_TITLE=Agent 中台系统

# 是否启用 Mock
VITE_USE_MOCK=false
EOF
echo -e "${GRAY}  ✓ 创建 .env.development${NC}"

# 创建 .env.production
cat > .env.production << 'EOF'
# API 基础 URL
VITE_API_BASE_URL=https://api.example.com

# 应用标题
VITE_APP_TITLE=Agent 中台系统

# 是否启用 Mock
VITE_USE_MOCK=false
EOF
echo -e "${GRAY}  ✓ 创建 .env.production${NC}"

# 创建 .prettierrc
cat > .prettierrc << 'EOF'
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
EOF
echo -e "${GRAY}  ✓ 创建 .prettierrc${NC}"

# 更新 vite.config.ts
cat > vite.config.ts << 'EOF'
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
EOF
echo -e "${GRAY}  ✓ 更新 vite.config.ts${NC}"

# 更新 tsconfig.json（添加路径别名）
cat > tsconfig.json << 'EOF'
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
EOF
echo -e "${GRAY}  ✓ 更新 tsconfig.json${NC}"

echo -e "${GREEN}✓ 配置文件创建完成${NC}"

# 创建基础文件
echo ""
echo -e "${GREEN}步骤 5/5: 创建基础文件...${NC}"

# 创建 API 类型定义
cat > src/shared/types/api.ts << 'EOF'
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
EOF
echo -e "${GRAY}  ✓ 创建 src/shared/types/api.ts${NC}"

# 创建全局样式
cat > src/shared/styles/global.css << 'EOF'
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
EOF
echo -e "${GRAY}  ✓ 创建 src/shared/styles/global.css${NC}"

# 创建主题配置
cat > src/shared/styles/theme.ts << 'EOF'
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
EOF
echo -e "${GRAY}  ✓ 创建 src/shared/styles/theme.ts${NC}"

# 创建 README
cat > README.md << 'EOF'
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

```bash
# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev

# 构建生产版本
pnpm build

# 预览生产版本
pnpm preview
```

## 目录结构

详见 `docs/frontend_setup_guide.md`

## 文档

- [前端结构规范](.augment/rules/frontend_structure.md)
- [开发文档](docs/develop_document.md)
- [初始化指南](docs/frontend_setup_guide.md)
EOF
echo -e "${GRAY}  ✓ 创建 README.md${NC}"

echo -e "${GREEN}✓ 基础文件创建完成${NC}"

# 返回项目根目录
cd ..

# 完成
echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}  ✓ 前端项目初始化完成！${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "${YELLOW}下一步操作:${NC}"
echo -e "${NC}  1. cd web${NC}"
echo -e "${NC}  2. pnpm dev${NC}"
echo ""
echo -e "${CYAN}项目将运行在: http://localhost:3000${NC}"
echo ""
echo -e "${YELLOW}详细文档请查看:${NC}"
echo -e "${NC}  - docs/frontend_setup_guide.md${NC}"
echo -e "${NC}  - .augment/rules/frontend_structure.md${NC}"
echo ""
