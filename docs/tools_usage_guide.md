# LangChain 工具使用指南

本文档说明如何使用 LangChain 工具。

---

## 📋 目录

1. [快速开始](#快速开始)
2. [HTTP 请求工具](#http-请求工具)
3. [文件读取工具](#文件读取工具)
4. [在 Agent 中使用工具](#在-agent-中使用工具)
5. [常见问题](#常见问题)

---

## 🚀 快速开始

### 步骤 1：导入工具

```python
from src.lc.tools import get_http_request_tool, get_read_file_tool, get_all_tools
```

### 步骤 2：获取工具

```python
# 获取单个工具
http_tool = get_http_request_tool()
file_tool = get_read_file_tool()

# 获取所有工具
tools = get_all_tools()
```

### 步骤 3：调用工具

```python
# 调用 HTTP 请求工具
result = http_tool.func(url="https://httpbin.org/get", method="GET")
print(result)

# 调用文件读取工具
result = file_tool.func(file_path="/path/to/file.txt")
print(result)
```

---

## 🌐 HTTP 请求工具

### 功能

发送 HTTP 请求（GET、POST、PUT、DELETE 等）并返回响应内容。

### API 说明

```python
http_request(
    url: str,                    # 请求的 URL（必填）
    method: str = "GET",         # HTTP 方法（默认：GET）
    headers: Optional[str] = None,  # 请求头，JSON 格式字符串（可选）
    body: Optional[str] = None,     # 请求体，JSON 格式字符串（可选）
) -> str
```

### 使用示例

#### 示例 1：GET 请求

```python
from src.lc.tools import get_http_request_tool

tool = get_http_request_tool()

# 发送 GET 请求
result = tool.func(
    url="https://api.github.com/users/octocat",
    method="GET",
)

print(result)
```

**输出**：
```
HTTP 200 - 成功

{
  "login": "octocat",
  "id": 1,
  "name": "The Octocat",
  ...
}
```

---

#### 示例 2：POST 请求

```python
from src.lc.tools import get_http_request_tool

tool = get_http_request_tool()

# 发送 POST 请求
result = tool.func(
    url="https://httpbin.org/post",
    method="POST",
    headers='{"Content-Type": "application/json"}',
    body='{"name": "John", "age": 30}',
)

print(result)
```

**输出**：
```
HTTP 200 - 成功

{
  "json": {
    "name": "John",
    "age": 30
  },
  ...
}
```

---

#### 示例 3：错误处理

```python
from src.lc.tools import get_http_request_tool

tool = get_http_request_tool()

# 无效 URL
result = tool.func(
    url="https://invalid-url-12345.com",
    method="GET",
)

print(result)
```

**输出**：
```
错误：无法连接到服务器
URL: https://invalid-url-12345.com
```

---

### 限制

- **超时时间**：30 秒
- **响应大小**：最多返回 10000 字符
- **支持的方法**：GET、POST、PUT、DELETE、PATCH、HEAD

---

## 📄 文件读取工具

### 功能

读取文本文件的内容。支持常见的文本文件格式（txt、json、csv、md 等）。

### API 说明

```python
read_file(
    file_path: str,  # 文件路径（绝对路径或相对路径）
) -> str
```

### 使用示例

#### 示例 1：读取文本文件

```python
from src.lc.tools import get_read_file_tool

tool = get_read_file_tool()

# 读取文本文件
result = tool.func(file_path="/path/to/file.txt")

print(result)
```

**输出**：
```
文件内容（编码：utf-8）：

Hello, World!
这是一个测试文件。
```

---

#### 示例 2：读取 JSON 文件

```python
from src.lc.tools import get_read_file_tool

tool = get_read_file_tool()

# 读取 JSON 文件
result = tool.func(file_path="/path/to/data.json")

print(result)
```

**输出**：
```
文件内容（编码：utf-8）：

{
  "name": "John",
  "age": 30
}
```

---

#### 示例 3：错误处理

```python
from src.lc.tools import get_read_file_tool

tool = get_read_file_tool()

# 文件不存在
result = tool.func(file_path="/path/to/nonexistent.txt")

print(result)
```

**输出**：
```
错误：文件不存在
路径：/path/to/nonexistent.txt
```

---

### 限制

- **文件大小**：最多 1 MB
- **返回内容**：最多返回 50000 字符
- **支持的编码**：UTF-8、GBK、GB2312、Latin-1

---

## 🤖 在 Agent 中使用工具

### 示例：创建简单的 Agent

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

from src.lc import get_llm_for_execution
from src.lc.tools import get_all_tools

# 获取所有工具
tools = get_all_tools()

# 创建 LLM
llm = get_llm_for_execution()

# 创建 Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有用的助手，可以使用工具来完成任务。"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 创建 Agent
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 调用 Agent
result = agent_executor.invoke({
    "input": "请访问 https://httpbin.org/get 并告诉我返回的内容"
})

print(result["output"])
```

---

## ❓ 常见问题

### 1. 如何添加自定义 headers？

**问题**：需要添加认证 token

**解决方案**：
```python
tool = get_http_request_tool()

result = tool.func(
    url="https://api.example.com/data",
    method="GET",
    headers='{"Authorization": "Bearer YOUR_TOKEN"}',
)
```

---

### 2. 如何处理大文件？

**问题**：文件超过 1 MB

**解决方案**：
- 工具会返回错误信息
- 可以考虑分块读取或使用其他方法

```python
tool = get_read_file_tool()

result = tool.func(file_path="/path/to/large_file.txt")

if "错误：文件太大" in result:
    print("文件太大，需要其他处理方式")
```

---

### 3. 如何处理非 UTF-8 编码的文件？

**问题**：文件使用 GBK 编码

**解决方案**：
- 工具会自动尝试多种编码（UTF-8、GBK、GB2312、Latin-1）
- 无需手动指定编码

```python
tool = get_read_file_tool()

# 自动检测编码
result = tool.func(file_path="/path/to/gbk_file.txt")
print(result)
```

---

### 4. 如何获取所有可用的工具？

**问题**：想知道有哪些工具可用

**解决方案**：
```python
from src.lc.tools import get_all_tools

tools = get_all_tools()

print("可用工具：")
for tool in tools:
    print(f"- {tool.name}: {tool.description[:50]}...")
```

**输出**：
```
可用工具：
- http_request: 发送 HTTP 请求并返回响应内容...
- read_file: 读取文件内容并返回...
```

---

### 5. 工具返回的错误信息如何处理？

**问题**：工具返回错误信息，如何判断？

**解决方案**：
```python
tool = get_http_request_tool()

result = tool.func(url="https://invalid-url.com", method="GET")

if "错误" in result or "error" in result.lower():
    print("请求失败：", result)
else:
    print("请求成功：", result)
```

---

## 📚 相关文档

- [工具实现总结](./tools_implementation_summary.md)
- [LangChain 官方文档 - Tools](https://python.langchain.com/docs/modules/tools/)

---

## 🎯 下一步

工具使用完成后，你可以：

1. ✅ 创建 TaskExecutorAgent
2. ✅ 集成到 ExecuteRunUseCase
3. ✅ 添加更多工具
