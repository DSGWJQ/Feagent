/**
 * 节点工具函数
 *
 * 用于节点状态管理、样式计算等
 */

export type NodeStatus = 'idle' | 'running' | 'completed' | 'error';

/**
 * 根据节点状态和选中状态获取样式类名
 */
export function getStatusColor(
  status: NodeStatus | undefined,
  selected: boolean
): string {
  switch (status) {
    case 'running':
      return 'node-running border-yellow-500 shadow-yellow-500/50';
    case 'completed':
      return 'node-completed border-green-500 shadow-green-500/50';
    case 'error':
      return 'node-error border-red-500 shadow-red-500/50';
    default:
      return selected ? 'selected border-primary shadow-lg' : 'border-border';
  }
}

/**
 * 获取节点默认配置
 */
export function getDefaultNodeData(type: string): Record<string, any> {
  switch (type) {
    case 'start':
      return {};
    case 'end':
      return {};
    case 'httpRequest':
      return {
        url: 'https://api.example.com',
        method: 'GET',
        headers: '{}',
        body: '{}',
      };
    case 'textModel':
      return {
        model: 'openai/gpt-5',
        temperature: 0.7,
        maxTokens: 2000,
        structuredOutput: false,
      };
    case 'embeddingModel':
      return {
        model: 'openai/text-embedding-3-small',
        dimensions: 1536,
      };
    case 'imageGeneration':
      return {
        model: 'gemini-2.5-flash-image',
        aspectRatio: '1:1',
        outputFormat: 'png',
      };
    case 'audio':
      return {
        model: 'openai/tts-1',
        voice: 'alloy',
        speed: 1.0,
      };
    case 'conditional':
      return {
        condition: "input1 === 'value'",
      };
    case 'javascript':
      return {
        code: '// Your code here\nreturn input1;',
      };
    case 'python':
      return {
        code: 'result = input1',
      };
    case 'prompt':
      return {
        content: 'Enter your prompt...',
      };
    case 'tool':
      return {
        // Canonical: workflow tool nodes reference a persisted Tool by stable ID.
        // Back-compat: keep optional name/description for display, but validation uses tool_id.
        tool_id: '',
        name: 'Tool',
        description: 'Select a tool from the library',
      };
    case 'structuredOutput':
      return {
        schemaName: 'MySchema',
        mode: 'object',
      };
    case 'database':
      return {
        database_url: 'sqlite:///agent_data.db',
        sql: 'SELECT * FROM table_name',
        params: {},
      };
    case 'transform':
      return {
        type: 'field_mapping',
        mapping: {},
      };
    case 'file':
      return {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
      };
    case 'notification':
      return {
        type: 'webhook',
        subject: 'Notification',
        message: 'Your message here',
        url: 'https://webhook.example.com',
        include_input: true,
      };
    case 'loop':
      return {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
      };
    default:
      return {};
  }
}

/**
 * 节点类型配置
 */
export interface NodeTypeConfig {
  type: string;
  label: string;
  description: string;
  color: string;
  icon: string;
}

export const nodeTypeConfigs: NodeTypeConfig[] = [
  {
    type: 'start',
    label: '开始',
    description: '工作流入口',
    color: '#52c41a',
    icon: 'Play',
  },
  {
    type: 'end',
    label: '结束',
    description: '工作流出口',
    color: '#ff4d4f',
    icon: 'Square',
  },
  {
    type: 'httpRequest',
    label: 'HTTP 请求',
    description: '调用外部 API',
    color: '#1890ff',
    icon: 'Globe',
  },
  {
    type: 'textModel',
    label: '文本模型',
    description: '使用 LLM 生成文本',
    color: '#722ed1',
    icon: 'MessageSquare',
  },
  {
    type: 'embeddingModel',
    label: '嵌入模型',
    description: '生成向量嵌入',
    color: '#13c2c2',
    icon: 'Layers',
  },
  {
    type: 'imageGeneration',
    label: '图像生成',
    description: '生成图片',
    color: '#fa8c16',
    icon: 'Image',
  },
  {
    type: 'audio',
    label: '音频',
    description: '生成语音',
    color: '#eb2f96',
    icon: 'Music',
  },
  {
    type: 'conditional',
    label: '条件分支',
    description: '基于条件进行分支',
    color: '#faad14',
    icon: 'GitBranch',
  },
  {
    type: 'javascript',
    label: 'JavaScript',
    description: '执行 JS 代码',
    color: '#f5222d',
    icon: 'Code',
  },
  {
    type: 'python',
    label: 'Python',
    description: '执行 Python 代码',
    color: '#faad14',
    icon: 'Code',
  },
  {
    type: 'prompt',
    label: '提示词',
    description: '输入文本或提示',
    color: '#a0d911',
    icon: 'FileText',
  },
  {
    type: 'tool',
    label: '工具',
    description: '自定义工具',
    color: '#2f54eb',
    icon: 'Wrench',
  },
  {
    type: 'structuredOutput',
    label: '结构化输出',
    description: '解析结构化数据',
    color: '#52c41a',
    icon: 'Database',
  },
  {
    type: 'database',
    label: '数据库',
    description: '执行 SQL 查询',
    color: '#1890ff',
    icon: 'Database',
  },
  {
    type: 'transform',
    label: '数据转换',
    description: '字段映射/过滤/聚合',
    color: '#faad14',
    icon: 'GitBranch',
  },
  {
    type: 'file',
    label: '文件',
    description: '文件读写操作',
    color: '#722ed1',
    icon: 'File',
  },
  {
    type: 'notification',
    label: '通知',
    description: '发送通知（Webhook/邮件）',
    color: '#fa8c16',
    icon: 'Bell',
  },
  {
    type: 'loop',
    label: '循环',
    description: '遍历数组或范围',
    color: '#1890ff',
    icon: 'Repeat',
  },
];
