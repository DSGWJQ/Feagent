# 前端架构总结（Frontend Architecture Summary）

本文件用于修复 README 的历史链接，并提供最小的架构入口说明。

## 技术栈

- Vite + React + TypeScript
- Ant Design
- TanStack Query
- React Router

## 核心路由契约（强制）

见 `web/src/app/router.tsx`：
- `/`：仅澄清对话（走 `/api/conversation/stream`），**绝不创建 workflow**
- `/workflows/new`：显式创建 workflow（走 `/api/workflows/chat-create/stream`）
- `/workflows/:id/edit`：编辑器（画布为 master）

## 实时通道

- 统一 SSE；前端不得创建 WebSocket（已有测试门禁）。
