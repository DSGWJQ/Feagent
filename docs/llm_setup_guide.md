# LLM 配置指南

本文档说明如何配置和测试 LLM（大语言模型）。

---

## 📋 目录

1. [支持的 LLM Provider](#支持的-llm-provider)
2. [配置步骤](#配置步骤)
3. [测试 LLM](#测试-llm)
4. [常见问题](#常见问题)

---

## 🎯 支持的 LLM Provider

本项目支持所有兼容 OpenAI 协议的 LLM Provider：

### 1. **OpenAI 官方**
- **模型**：gpt-4o-mini, gpt-4o, gpt-4-turbo 等
- **Base URL**：`https://api.openai.com/v1`
- **获取 API Key**：https://platform.openai.com/api-keys

### 2. **KIMI (Moonshot AI)** ⭐ 推荐
- **模型**：moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k
- **Base URL**：`https://api.moonshot.cn/v1`
- **获取 API Key**：https://platform.moonshot.cn/console/api-keys
- **优势**：
  - ✅ 兼容 OpenAI 协议
  - ✅ 支持中文
  - ✅ 价格便宜
  - ✅ 国内访问速度快

### 3. **其他兼容 Provider**
- Azure OpenAI
- 本地模型（如 Ollama、LM Studio）
- 其他云服务商（如阿里云、腾讯云）

---

## ⚙️ 配置步骤

### 步骤 1：获取 API Key

#### 如果使用 KIMI：
1. 访问 https://platform.moonshot.cn/
2. 注册/登录账号
3. 进入"API Keys"页面
4. 创建新的 API Key
5. 复制 API Key（格式：`sk-...`）

#### 如果使用 OpenAI：
1. 访问 https://platform.openai.com/
2. 注册/登录账号
3. 进入"API Keys"页面
4. 创建新的 API Key
5. 复制 API Key（格式：`sk-...`）

### 步骤 2：配置 `.env` 文件

打开项目根目录的 `.env` 文件，找到 LLM 配置部分：

```bash
# LLM Provider (OpenAI 兼容)
#
# 选项 1: OpenAI 官方
# OPENAI_API_KEY=sk-your-openai-api-key-here
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_MODEL=gpt-4o-mini
#
# 选项 2: KIMI (Moonshot AI) - 兼容 OpenAI 协议
# OPENAI_API_KEY=sk-your-kimi-api-key-here
# OPENAI_BASE_URL=https://api.moonshot.cn/v1
# OPENAI_MODEL=moonshot-v1-8k
#
# 当前配置（请根据你的实际情况修改）：
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.moonshot.cn/v1
OPENAI_MODEL=moonshot-v1-8k
```

#### 如果使用 KIMI：
```bash
OPENAI_API_KEY=sk-你的KIMI-API-Key
OPENAI_BASE_URL=https://api.moonshot.cn/v1
OPENAI_MODEL=moonshot-v1-8k
```

#### 如果使用 OpenAI：
```bash
OPENAI_API_KEY=sk-你的OpenAI-API-Key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

### 步骤 3：保存文件

保存 `.env` 文件后，配置就完成了！

---

## 🧪 测试 LLM

### 方法 1：使用测试脚本（推荐）

运行测试脚本，验证 LLM 配置是否正确：

```bash
python scripts/test_llm.py
```

**预期输出**：
```
============================================================
测试 LLM 配置
============================================================

1. 检查配置
   API Key: sk-xxxxxxxx...
   Base URL: https://api.moonshot.cn/v1
   Model: moonshot-v1-8k

2. 创建 LLM 客户端
   ✅ 通用 LLM 创建成功
   ✅ 计划生成 LLM 创建成功
   ✅ 任务执行 LLM 创建成功

3. 测试 LLM 调用
   发送测试消息：'你好，请用一句话介绍你自己'
   ✅ 调用成功
   响应：我是 Kimi，由月之暗面科技有限公司开发的人工智能助手...

============================================================
✅ 所有测试通过！LLM 配置正确
============================================================
```

### 方法 2：在 Python 代码中测试

```python
from src.lc import get_llm

# 创建 LLM 客户端
llm = get_llm()

# 调用 LLM
response = llm.invoke("你好，请介绍一下自己")
print(response.content)
```

---

## ❓ 常见问题

### 1. 错误：`OPENAI_API_KEY 未配置`

**原因**：`.env` 文件中的 `OPENAI_API_KEY` 未设置或为默认值

**解决方案**：
1. 打开 `.env` 文件
2. 将 `OPENAI_API_KEY=your-api-key-here` 替换为你的真实 API Key
3. 保存文件

### 2. 错误：`Connection Error` 或 `Timeout`

**原因**：网络连接问题或 Base URL 配置错误

**解决方案**：
1. 检查网络连接
2. 确认 `OPENAI_BASE_URL` 配置正确
   - KIMI: `https://api.moonshot.cn/v1`
   - OpenAI: `https://api.openai.com/v1`
3. 如果使用 OpenAI，可能需要配置代理

### 3. 错误：`Invalid API Key` 或 `Unauthorized`

**原因**：API Key 无效或已过期

**解决方案**：
1. 检查 API Key 是否正确（包括前缀 `sk-`）
2. 检查 API Key 是否已过期
3. 重新生成 API Key

### 4. 错误：`Model not found`

**原因**：模型名称配置错误

**解决方案**：
1. 检查 `OPENAI_MODEL` 配置
2. 确认模型名称正确：
   - KIMI: `moonshot-v1-8k`, `moonshot-v1-32k`, `moonshot-v1-128k`
   - OpenAI: `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`

### 5. 如何切换到其他 LLM Provider？

只需修改 `.env` 文件中的配置：

```bash
# 切换到 OpenAI
OPENAI_API_KEY=sk-你的OpenAI-API-Key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# 或切换到 KIMI
OPENAI_API_KEY=sk-你的KIMI-API-Key
OPENAI_BASE_URL=https://api.moonshot.cn/v1
OPENAI_MODEL=moonshot-v1-8k
```

---

## 📚 相关文档

- [LangChain 官方文档](https://python.langchain.com/)
- [KIMI API 文档](https://platform.moonshot.cn/docs)
- [OpenAI API 文档](https://platform.openai.com/docs)

---

## 🎯 下一步

LLM 配置完成后，你可以：

1. ✅ 实现计划生成（Plan Generation）
2. ✅ 实现任务执行（Task Execution）
3. ✅ 集成到 ExecuteRunUseCase

详见：[LangChain 集成指南](./langchain_integration_guide.md)（待创建）
