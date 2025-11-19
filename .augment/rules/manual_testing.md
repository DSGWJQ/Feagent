# 手动测试规则

## 规则说明

当开发涉及前后端交互、UI界面展示、或需要实际运行环境验证的功能时，AI应该：

1. **不要自动启动服务** - 不要使用 `launch-process` 启动前端或后端服务
2. **提供测试指南** - 明确告诉用户如何手动启动和测试
3. **说明测试要点** - 列出需要验证的功能点和预期效果

## 适用场景

- 前端UI组件开发完成后
- 前后端API集成完成后
- 需要浏览器环境验证的功能
- 需要数据库或外部服务的功能
- 工作流执行等复杂交互

## 测试指南模板

### 前端测试

```bash
# 1. 启动前端开发服务器
cd web
npm run dev

# 2. 打开浏览器访问
# http://localhost:5173
```

### 后端测试

```bash
# 1. 激活虚拟环境（如果有）
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 2. 启动后端服务
cd src
uvicorn main:app --reload --port 8000

# 3. 访问API文档
# http://localhost:8000/docs
```

### 全栈测试

```bash
# 终端1: 启动后端
cd src
uvicorn main:app --reload --port 8000

# 终端2: 启动前端
cd web
npm run dev

# 浏览器访问: http://localhost:5173
```

## 测试报告要求

用户测试后应反馈：
- ✅ 功能是否正常工作
- ❌ 遇到的问题和错误信息
- 📸 截图（如果是UI问题）
- 💡 改进建议

