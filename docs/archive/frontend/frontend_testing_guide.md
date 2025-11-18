# 前端测试指南

## 📋 概述

本文档介绍前端测试的配置、编写和运行方法。

**测试框架**: Vitest + React Testing Library
**测试覆盖**: API 客户端、Hooks、组件
**测试结果**: ✅ 20/20 测试通过

---

## ✅ 测试配置

### 1. Vitest 配置

**文件**: `web/vitest.config.ts`

```typescript
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,              // 全局 API（describe, it, expect）
    environment: 'jsdom',       // 浏览器环境模拟
    setupFiles: ['./src/test/setup.ts'],  // 测试前执行
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'src/test/', '**/*.d.ts'],
    },
  },
});
```

### 2. 测试环境设置

**文件**: `web/src/test/setup.ts`

```typescript
import { expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';

// 扩展 expect 断言
expect.extend(matchers);

// 每个测试后自动清理 DOM
afterEach(() => {
  cleanup();
});

// Mock window.matchMedia（Ant Design 需要）
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    // ...
  })),
});
```

### 3. 测试工具函数

**文件**: `web/src/test/utils.tsx`

```typescript
// 创建测试用的 QueryClient
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,      // 测试时不重试
        gcTime: 0,         // 不缓存
        staleTime: 0,
      },
    },
  });
}

// 自定义渲染函数（自动包装 Provider）
export function renderWithProviders(ui: ReactElement) {
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <ConfigProvider locale={zhCN} theme={theme}>
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </ConfigProvider>
    );
  }

  return {
    ...render(ui, { wrapper: Wrapper }),
    queryClient,
  };
}
```

---

## 📝 测试编写

### 1. API 客户端测试

**文件**: `web/src/features/agents/api/__tests__/agentsApi.test.ts`

**测试内容**:
- ✅ 验证 API 调用的正确性
- ✅ 验证请求参数的传递
- ✅ 验证响应数据的返回

**示例**:
```typescript
describe('agentsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('应该调用 GET /agents', async () => {
    // Arrange: 准备测试数据
    const mockAgents: Agent[] = [{ id: '1', name: '测试' }];
    vi.mocked(request.get).mockResolvedValue(mockAgents);

    // Act: 执行测试
    const result = await agentsApi.getAgents();

    // Assert: 验证结果
    expect(request.get).toHaveBeenCalledWith('/agents', { params: undefined });
    expect(result).toEqual(mockAgents);
  });
});
```

**为什么要测试 API 客户端？**
1. 确保 API 调用的正确性
2. 作为 API 使用的文档
3. 重构时的安全网

---

### 2. Hooks 测试

**文件**: `web/src/shared/hooks/__tests__/useAgents.test.tsx`

**测试内容**:
- ✅ 验证 Hooks 是否正确调用 API
- ✅ 验证缓存机制是否正常工作
- ✅ 验证 Mutation 后是否正确刷新缓存

**示例**:
```typescript
describe('useAgents', () => {
  it('应该成功获取 Agent 列表', async () => {
    // Arrange
    const mockAgents: Agent[] = [{ id: '1', name: '测试' }];
    vi.mocked(agentsApi.getAgents).mockResolvedValue(mockAgents);

    // Act
    const { result } = renderHook(() => useAgents(), {
      wrapper: createWrapper(),
    });

    // Assert
    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockAgents);
  });
});
```

**为什么要测试 Hooks？**
1. Hooks 包含业务逻辑（缓存、刷新等）
2. 确保 Mutation 后缓存正确更新
3. 作为 Hooks 使用的文档

---

### 3. 组件测试

**文件**: `web/src/features/agents/pages/__tests__/AgentListTest.test.tsx`

**测试内容**:
- ✅ 验证组件是否正确渲染
- ✅ 验证用户交互是否正常工作
- ✅ 验证不同状态下的显示

**示例**:
```typescript
describe('AgentListTest', () => {
  it('应该显示 Agent 列表', async () => {
    // Arrange
    const mockAgents: Agent[] = [
      { id: '1', name: '测试 Agent 1' },
      { id: '2', name: '测试 Agent 2' },
    ];
    vi.mocked(agentsApi.getAgents).mockResolvedValue(mockAgents);

    // Act
    renderWithProviders(<AgentListTest />);

    // Assert
    await waitFor(() => {
      expect(screen.getByText('✅ API 连接成功！')).toBeInTheDocument();
    });

    expect(screen.getByText('测试 Agent 1')).toBeInTheDocument();
    expect(screen.getByText('测试 Agent 2')).toBeInTheDocument();
  });

  it('应该能够创建测试 Agent', async () => {
    // Arrange
    const user = userEvent.setup();
    vi.mocked(agentsApi.getAgents).mockResolvedValue([]);
    vi.mocked(agentsApi.createAgent).mockResolvedValue(mockNewAgent);

    // Act
    renderWithProviders(<AgentListTest />);
    const createButton = screen.getByRole('button', { name: /创建测试 Agent/ });
    await user.click(createButton);

    // Assert
    await waitFor(() => {
      expect(agentsApi.createAgent).toHaveBeenCalled();
    });
  });
});
```

**为什么要测试组件？**
1. 确保组件在不同状态下正确渲染
2. 确保用户交互正常工作
3. 防止重构时破坏功能
4. 作为组件使用的文档

---

## 🚀 运行测试

### 1. 运行所有测试

```bash
cd web
pnpm test
```

**输出**:
```
✓ src/features/agents/api/__tests__/agentsApi.test.ts (6 tests)
✓ src/shared/hooks/__tests__/useAgents.test.tsx (7 tests)
✓ src/features/agents/pages/__tests__/AgentListTest.test.tsx (7 tests)

Test Files  3 passed (3)
Tests  20 passed (20)
```

### 2. 监听模式（开发时使用）

```bash
pnpm test:watch
```

**特点**:
- 文件修改时自动重新运行测试
- 只运行相关的测试
- 提供交互式菜单

### 3. 生成覆盖率报告

```bash
pnpm test:coverage
```

**输出**:
- 终端显示覆盖率统计
- 生成 HTML 报告（`coverage/index.html`）

---

## 📊 测试结果

### 当前测试覆盖

| 测试类型 | 文件数 | 测试数 | 状态 |
|---------|-------|-------|------|
| API 客户端 | 1 | 6 | ✅ 通过 |
| Hooks | 1 | 7 | ✅ 通过 |
| 组件 | 1 | 7 | ✅ 通过 |
| **总计** | **3** | **20** | **✅ 100%** |

### 测试详情

#### API 客户端测试（6 个）
- ✅ getAgents - 调用 GET /agents
- ✅ getAgents - 传递查询参数
- ✅ getAgent - 调用 GET /agents/:id
- ✅ createAgent - 调用 POST /agents
- ✅ updateAgent - 调用 PUT /agents/:id
- ✅ deleteAgent - 调用 DELETE /agents/:id

#### Hooks 测试（7 个）
- ✅ useAgents - 成功获取列表
- ✅ useAgents - 传递查询参数
- ✅ useAgents - 处理错误
- ✅ useAgent - 成功获取单个 Agent
- ✅ useAgent - id 为空时不发起请求
- ✅ useCreateAgent - 成功创建 Agent
- ✅ useDeleteAgent - 成功删除 Agent

#### 组件测试（7 个）
- ✅ 显示加载中状态
- ✅ 显示 Agent 列表
- ✅ 显示空状态
- ✅ 显示错误信息
- ✅ 能够创建测试 Agent
- ✅ 能够刷新列表
- ✅ 能够删除 Agent

---

## 🎯 测试最佳实践

### 1. AAA 模式

```typescript
it('测试描述', async () => {
  // Arrange: 准备测试数据
  const mockData = { ... };
  vi.mocked(api).mockResolvedValue(mockData);

  // Act: 执行测试
  const result = await someFunction();

  // Assert: 验证结果
  expect(result).toEqual(mockData);
});
```

### 2. 使用 Mock

```typescript
// Mock 整个模块
vi.mock('@/features/agents/api/agentsApi', () => ({
  agentsApi: {
    getAgents: vi.fn(),
    createAgent: vi.fn(),
  },
}));

// 设置 Mock 返回值
vi.mocked(agentsApi.getAgents).mockResolvedValue([]);

// 验证 Mock 调用
expect(agentsApi.getAgents).toHaveBeenCalledWith(params);
```

### 3. 等待异步操作

```typescript
// 等待元素出现
await waitFor(() => {
  expect(screen.getByText('加载完成')).toBeInTheDocument();
});

// 等待元素消失
await waitFor(() => {
  expect(screen.queryByText('加载中')).not.toBeInTheDocument();
});
```

### 4. 用户交互模拟

```typescript
const user = userEvent.setup();

// 点击按钮
await user.click(screen.getByRole('button', { name: '提交' }));

// 输入文本
await user.type(screen.getByRole('textbox'), 'Hello');

// 选择下拉框
await user.selectOptions(screen.getByRole('combobox'), 'option1');
```

---

## 📚 常用断言

### 1. 元素存在性

```typescript
expect(screen.getByText('文本')).toBeInTheDocument();
expect(screen.queryByText('文本')).not.toBeInTheDocument();
```

### 2. 元素状态

```typescript
expect(button).toBeDisabled();
expect(button).toBeEnabled();
expect(checkbox).toBeChecked();
```

### 3. 数据验证

```typescript
expect(result).toEqual(expected);
expect(result).toHaveLength(3);
expect(array).toContain(item);
```

### 4. 函数调用

```typescript
expect(mockFn).toHaveBeenCalled();
expect(mockFn).toHaveBeenCalledTimes(2);
expect(mockFn).toHaveBeenCalledWith(arg1, arg2);
```

---

## 🔧 故障排除

### 问题 1: 找不到元素

**错误**: `Unable to find an element with the text: ...`

**解决方案**:
1. 使用 `screen.debug()` 查看当前 DOM
2. 检查元素是否异步加载（使用 `waitFor`）
3. 检查文本是否完全匹配（使用正则表达式）

### 问题 2: Mock 不生效

**错误**: Mock 函数没有被调用

**解决方案**:
1. 确保 `vi.mock()` 在测试文件顶部
2. 使用 `vi.clearAllMocks()` 清除之前的 Mock
3. 检查 Mock 路径是否正确

### 问题 3: 异步测试超时

**错误**: `Timeout - Async callback was not invoked within the 5000 ms timeout`

**解决方案**:
1. 使用 `await waitFor()` 等待异步操作
2. 增加超时时间（不推荐）
3. 检查 Promise 是否正确 resolve

---

## 📝 总结

### 完成的工作

1. ✅ 配置 Vitest 测试环境
2. ✅ 创建测试工具函数
3. ✅ 编写 API 客户端测试（6 个）
4. ✅ 编写 Hooks 测试（7 个）
5. ✅ 编写组件测试（7 个）

**总计**: 20 个测试，100% 通过 ✅

### 测试的价值

1. **质量保证**: 确保代码按预期工作
2. **重构安全**: 修改代码时不会破坏功能
3. **文档作用**: 测试本身就是最好的使用文档
4. **开发效率**: 快速发现问题，减少调试时间

### 下一步

现在前端已经有了完整的测试覆盖，可以放心地：
1. 使用 V0 生成 UI 组件
2. 重构现有代码
3. 添加新功能

**测试是前端开发的安全网！** 🛡️
