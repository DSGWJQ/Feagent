# 工作流前端设计文档

## 📋 概述

本文档详细定义工作流相关的所有前端组件、页面、Hooks 和类型定义。

---

## 🎯 页面结构

```
/workflows
  ├── /                    - 工作流列表页
  ├── /create              - 创建工作流（Modal，不是独立页面）
  ├── /:id                 - 工作流详情页（只读）
  └── /:id/edit            - 工作流编辑页（对话 + 拖拽）
```

---

## 📊 组件架构

### 1. 页面组件

#### WorkflowListPage（工作流列表页）
```tsx
// web/src/features/workflows/pages/WorkflowListPage.tsx

export function WorkflowListPage() {
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const { data: workflows, isLoading } = useWorkflows();

  return (
    <PageContainer>
      <ProTable
        dataSource={workflows}
        columns={[
          { title: '名称', dataIndex: 'name' },
          { title: '描述', dataIndex: 'description' },
          { title: '状态', dataIndex: 'status' },
          { title: '创建时间', dataIndex: 'created_at' },
          { title: '操作', render: (_, record) => (
            <>
              <Button onClick={() => navigate(`/workflows/${record.id}`)}>
                查看
              </Button>
              <Button onClick={() => navigate(`/workflows/${record.id}/edit`)}>
                编辑
              </Button>
              <Button onClick={() => deleteWorkflow(record.id)}>
                删除
              </Button>
            </>
          )}
        ]}
        toolBarRender={() => [
          <Button
            type="primary"
            onClick={() => setCreateModalOpen(true)}
          >
            创建工作流
          </Button>
        ]}
      />

      <CreateWorkflowModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={(workflow) => {
          navigate(`/workflows/${workflow.id}/edit`);
        }}
      />
    </PageContainer>
  );
}
```

---

#### WorkflowDetailPage（工作流详情页）
```tsx
// web/src/features/workflows/pages/WorkflowDetailPage.tsx

export function WorkflowDetailPage() {
  const { id } = useParams();
  const { data: workflow, isLoading } = useWorkflow(id);

  return (
    <PageContainer>
      <ProDescriptions
        title={workflow.name}
        dataSource={workflow}
        columns={[
          { title: '描述', dataIndex: 'description' },
          { title: '状态', dataIndex: 'status' },
          { title: '创建时间', dataIndex: 'created_at' },
          { title: '更新时间', dataIndex: 'updated_at' }
        ]}
      />

      <Card title="工作流图表">
        <WorkflowViewer workflow={workflow} readOnly />
      </Card>

      <Button onClick={() => navigate(`/workflows/${id}/edit`)}>
        编辑工作流
      </Button>
    </PageContainer>
  );
}
```

---

#### WorkflowEditorPage（工作流编辑页）
```tsx
// web/src/features/workflows/pages/WorkflowEditorPage.tsx

export function WorkflowEditorPage() {
  const { id } = useParams();
  const { data: workflow, isLoading } = useWorkflow(id);
  const updateWorkflow = useUpdateWorkflow();

  return (
    <PageContainer>
      <div className="workflow-editor">
        <div className="left-panel">
          <WorkflowCanvas
            workflow={workflow}
            onSave={(updatedWorkflow) => {
              updateWorkflow.mutate({
                id,
                data: updatedWorkflow
              });
            }}
          />
        </div>

        <div className="right-panel">
          <WorkflowChat
            workflowId={id}
            onWorkflowUpdated={(updatedWorkflow) => {
              // 自动刷新工作流
              refetch();
            }}
          />
        </div>
      </div>
    </PageContainer>
  );
}
```

---

### 2. 核心组件

#### CreateWorkflowModal（创建工作流弹窗）
```tsx
// web/src/features/workflows/components/CreateWorkflowModal.tsx

interface CreateWorkflowModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (workflow: Workflow) => void;
}

export function CreateWorkflowModal({
  open,
  onClose,
  onSuccess
}: CreateWorkflowModalProps) {
  const createWorkflow = useCreateWorkflow();

  return (
    <Modal
      title="创建工作流"
      open={open}
      onCancel={onClose}
      footer={null}
    >
      <ProForm
        onFinish={async (values) => {
          const workflow = await createWorkflow.mutateAsync(values);
          onSuccess(workflow);
          onClose();
        }}
      >
        <ProFormText
          name="start"
          label="起点"
          placeholder="例如：GitHub Issue 列表"
          rules={[{ required: true, message: '请输入起点' }]}
        />

        <ProFormText
          name="goal"
          label="终点"
          placeholder="例如：发送到钉钉群"
          rules={[{ required: true, message: '请输入终点' }]}
        />

        <ProFormTextArea
          name="description"
          label="描述"
          placeholder="例如：每天定时获取 GitHub Issue 并发送到钉钉群"
        />
      </ProForm>
    </Modal>
  );
}
```

---

#### WorkflowCanvas（工作流画布）
```tsx
// web/src/features/workflows/components/WorkflowCanvas.tsx

import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState
} from 'reactflow';
import 'reactflow/dist/style.css';

interface WorkflowCanvasProps {
  workflow: Workflow;
  onSave: (workflow: Workflow) => void;
  readOnly?: boolean;
}

export function WorkflowCanvas({
  workflow,
  onSave,
  readOnly = false
}: WorkflowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(
    workflow.nodes.map(node => ({
      id: node.id,
      type: 'custom',
      position: node.position,
      data: {
        type: node.type,
        name: node.name,
        config: node.config,
        status: node.status // 执行状态
      }
    }))
  );

  const [edges, setEdges, onEdgesChange] = useEdgesState(
    workflow.edges.map(edge => ({
      id: edge.id,
      source: edge.source_node_id,
      target: edge.target_node_id
    }))
  );

  const handleSave = () => {
    const updatedWorkflow = {
      ...workflow,
      nodes: nodes.map(node => ({
        id: node.id,
        type: node.data.type,
        name: node.data.name,
        config: node.data.config,
        position: node.position
      })),
      edges: edges.map(edge => ({
        id: edge.id,
        source_node_id: edge.source,
        target_node_id: edge.target
      }))
    };

    onSave(updatedWorkflow);
  };

  return (
    <div style={{ width: '100%', height: '600px' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={readOnly ? undefined : onNodesChange}
        onEdgesChange={readOnly ? undefined : onEdgesChange}
        nodeTypes={{
          custom: NodeWithStatus
        }}
        fitView
      >
        <Controls />
        <Background />
      </ReactFlow>

      {!readOnly && (
        <Button
          type="primary"
          onClick={handleSave}
          style={{ marginTop: 16 }}
        >
          保存工作流
        </Button>
      )}
    </div>
  );
}
```

---

#### NodeWithStatus（带状态的节点）
```tsx
// web/src/features/workflows/components/NodeWithStatus.tsx

import { Handle, Position } from 'reactflow';

interface NodeWithStatusProps {
  data: {
    type: NodeType;
    name: string;
    config: any;
    status?: NodeExecutionStatus;
  };
}

export function NodeWithStatus({ data }: NodeWithStatusProps) {
  const getStatusColor = (status?: NodeExecutionStatus) => {
    switch (status) {
      case 'succeeded':
        return '#52c41a'; // 绿色
      case 'failed':
        return '#ff4d4f'; // 红色
      case 'running':
        return '#faad14'; // 黄色
      case 'pending':
      default:
        return '#d9d9d9'; // 灰色
    }
  };

  const getStatusIcon = (status?: NodeExecutionStatus) => {
    switch (status) {
      case 'succeeded':
        return '✅';
      case 'failed':
        return '❌';
      case 'running':
        return '⏳';
      case 'pending':
      default:
        return '⏸️';
    }
  };

  return (
    <div
      style={{
        padding: 16,
        border: `2px solid ${getStatusColor(data.status)}`,
        borderRadius: 8,
        background: '#fff',
        minWidth: 150
      }}
    >
      <Handle type="target" position={Position.Top} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 20 }}>
          {getStatusIcon(data.status)}
        </span>
        <div>
          <div style={{ fontWeight: 'bold' }}>{data.name}</div>
          <div style={{ fontSize: 12, color: '#999' }}>
            {data.type.toUpperCase()}
          </div>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

---

#### WorkflowChat（工作流对话框）
```tsx
// web/src/features/workflows/components/WorkflowChat.tsx

interface WorkflowChatProps {
  workflowId: string;
  onWorkflowUpdated: (workflow: Workflow) => void;
}

export function WorkflowChat({
  workflowId,
  onWorkflowUpdated
}: WorkflowChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const updateWorkflowByChat = useUpdateWorkflowByChat();

  const handleSend = async () => {
    if (!input.trim()) return;

    // 添加用户消息
    setMessages(prev => [...prev, {
      role: 'user',
      content: input
    }]);

    // 调用 API
    const result = await updateWorkflowByChat.mutateAsync({
      workflowId,
      message: input
    });

    // 添加 AI 回复
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: result.ai_message
    }]);

    // 通知父组件工作流已更新
    onWorkflowUpdated(result.workflow);

    setInput('');
  };

  return (
    <div className="workflow-chat">
      <div className="messages">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`message ${msg.role}`}
          >
            {msg.content}
          </div>
        ))}
      </div>

      <div className="input-area">
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入调整需求，例如：在发送钉钉之前，先保存到数据库"
          rows={3}
        />
        <Button
          type="primary"
          onClick={handleSend}
          loading={updateWorkflowByChat.isPending}
        >
          发送
        </Button>
      </div>
    </div>
  );
}
```

---

#### WorkflowViewer（工作流查看器）
```tsx
// web/src/features/workflows/components/WorkflowViewer.tsx

interface WorkflowViewerProps {
  workflow: Workflow;
  readOnly?: boolean;
}

export function WorkflowViewer({
  workflow,
  readOnly = true
}: WorkflowViewerProps) {
  return (
    <WorkflowCanvas
      workflow={workflow}
      onSave={() => {}}
      readOnly={readOnly}
    />
  );
}
```

---

### 3. Hooks

#### useWorkflows（获取工作流列表）
```tsx
// web/src/shared/hooks/useWorkflows.ts

export function useWorkflows(params?: {
  page?: number;
  page_size?: number;
  status?: WorkflowStatus;
  search?: string;
}) {
  return useQuery({
    queryKey: ['workflows', params],
    queryFn: () => workflowsApi.getWorkflows(params)
  });
}
```

---

#### useWorkflow（获取工作流详情）
```tsx
export function useWorkflow(id: string) {
  return useQuery({
    queryKey: ['workflows', id],
    queryFn: () => workflowsApi.getWorkflow(id),
    enabled: !!id
  });
}
```

---

#### useCreateWorkflow（创建工作流）
```tsx
export function useCreateWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateWorkflowRequest) =>
      workflowsApi.createWorkflow(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    }
  });
}
```

---

#### useUpdateWorkflow（更新工作流）
```tsx
export function useUpdateWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateWorkflowRequest }) =>
      workflowsApi.updateWorkflow(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['workflows', id] });
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    }
  });
}
```

---

#### useUpdateWorkflowByChat（对话式更新工作流）
```tsx
export function useUpdateWorkflowByChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ workflowId, message }: {
      workflowId: string;
      message: string;
    }) => workflowsApi.updateWorkflowByChat(workflowId, message),
    onSuccess: (_, { workflowId }) => {
      queryClient.invalidateQueries({ queryKey: ['workflows', workflowId] });
    }
  });
}
```

---

#### useDeleteWorkflow（删除工作流）
```tsx
export function useDeleteWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => workflowsApi.deleteWorkflow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    }
  });
}
```

---

#### useWorkflowRun（执行工作流 + SSE 状态更新）
```tsx
export function useWorkflowRun(workflowId: string, runId?: string) {
  const [nodeStatuses, setNodeStatuses] = useState<
    Record<string, NodeExecutionStatus>
  >({});

  useEffect(() => {
    if (!runId) return;

    // 建立 SSE 连接
    const eventSource = new EventSource(
      `/workflows/${workflowId}/runs/${runId}/events`
    );

    eventSource.addEventListener('node_execution_started', (e) => {
      const data = JSON.parse(e.data);
      setNodeStatuses(prev => ({
        ...prev,
        [data.node_id]: 'running'
      }));
    });

    eventSource.addEventListener('node_execution_completed', (e) => {
      const data = JSON.parse(e.data);
      setNodeStatuses(prev => ({
        ...prev,
        [data.node_id]: data.status
      }));
    });

    eventSource.addEventListener('node_execution_failed', (e) => {
      const data = JSON.parse(e.data);
      setNodeStatuses(prev => ({
        ...prev,
        [data.node_id]: 'failed'
      }));
    });

    eventSource.addEventListener('run_completed', (e) => {
      eventSource.close();
    });

    return () => {
      eventSource.close();
    };
  }, [workflowId, runId]);

  return { nodeStatuses };
}
```

---

### 4. 类型定义

```tsx
// web/src/shared/types/workflow.ts

export enum WorkflowStatus {
  DRAFT = 'draft',
  ACTIVE = 'active',
  ARCHIVED = 'archived'
}

export enum NodeType {
  HTTP = 'http',
  SQL = 'sql',
  SCRIPT = 'script',
  TRANSFORM = 'transform'
}

export enum NodeExecutionStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  SUCCEEDED = 'succeeded',
  FAILED = 'failed',
  SKIPPED = 'skipped'
}

export interface Position {
  x: number;
  y: number;
}

export interface Node {
  id: string;
  type: NodeType;
  name: string;
  config: Record<string, any>;
  position: Position;
}

export interface Edge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  condition?: string;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  nodes: Node[];
  edges: Edge[];
  status: WorkflowStatus;
  created_at: string;
  updated_at: string;
}

export interface NodeExecution {
  id: string;
  node_id: string;
  status: NodeExecutionStatus;
  input_data: Record<string, any>;
  output_data?: Record<string, any>;
  error_message?: string;
  started_at?: string;
  finished_at?: string;
}

export interface Run {
  id: string;
  workflow_id: string;
  status: RunStatus;
  input_data: Record<string, any>;
  node_executions: NodeExecution[];
  started_at?: string;
  finished_at?: string;
}

export interface CreateWorkflowRequest {
  start: string;
  goal: string;
  description?: string;
}

export interface UpdateWorkflowRequest {
  nodes: Node[];
  edges: Edge[];
}

export interface CreateWorkflowResponse {
  workflow: Workflow;
  ai_message: string;
}

export interface UpdateWorkflowByChatResponse {
  workflow: Workflow;
  ai_message: string;
}
```

---

## 📁 文件结构

```
web/src/
├── features/
│   └── workflows/
│       ├── pages/
│       │   ├── WorkflowListPage.tsx
│       │   ├── WorkflowDetailPage.tsx
│       │   └── WorkflowEditorPage.tsx
│       ├── components/
│       │   ├── CreateWorkflowModal.tsx
│       │   ├── WorkflowCanvas.tsx
│       │   ├── NodeWithStatus.tsx
│       │   ├── WorkflowChat.tsx
│       │   └── WorkflowViewer.tsx
│       └── api/
│           └── workflowsApi.ts
├── shared/
│   ├── hooks/
│   │   └── useWorkflows.ts
│   └── types/
│       └── workflow.ts
└── app/
    └── routes.tsx
```

---

## ✅ 总结

本文档定义了工作流相关的所有前端组件、页面、Hooks 和类型定义，包括：

1. ✅ 3 个页面组件（列表、详情、编辑）
2. ✅ 6 个核心组件（创建弹窗、画布、节点、对话框、查看器）
3. ✅ 7 个 Hooks（CRUD + 对话调整 + SSE 状态更新）
4. ✅ 完整的类型定义

所有组件遵循 React 19 + TypeScript + Ant Design Pro 规范，使用 TanStack Query 管理状态，使用 React Flow 实现工作流可视化。
