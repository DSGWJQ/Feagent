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
      return 'border-yellow-500 shadow-yellow-500/50';
    case 'completed':
      return 'border-green-500 shadow-green-500/50';
    case 'error':
      return 'border-red-500 shadow-red-500/50';
    default:
      return selected ? 'border-primary shadow-lg' : 'border-border';
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
    case 'prompt':
      return {
        content: 'Enter your prompt...',
      };
    case 'tool':
      return {
        name: 'myTool',
        description: 'Tool description',
        code: 'async function execute(args) {\n  return result;\n}',
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
    label: 'Start',
    description: 'Workflow entry point',
    color: '#52c41a',
    icon: 'Play',
  },
  {
    type: 'end',
    label: 'End',
    description: 'Workflow exit point',
    color: '#ff4d4f',
    icon: 'Square',
  },
  {
    type: 'httpRequest',
    label: 'HTTP Request',
    description: 'Call external APIs',
    color: '#1890ff',
    icon: 'Globe',
  },
  {
    type: 'textModel',
    label: 'Text Model',
    description: 'Generate text with LLM',
    color: '#722ed1',
    icon: 'MessageSquare',
  },
  {
    type: 'embeddingModel',
    label: 'Embedding Model',
    description: 'Generate embeddings',
    color: '#13c2c2',
    icon: 'Layers',
  },
  {
    type: 'imageGeneration',
    label: 'Image Generation',
    description: 'Generate images',
    color: '#fa8c16',
    icon: 'Image',
  },
  {
    type: 'audio',
    label: 'Audio',
    description: 'Generate audio',
    color: '#eb2f96',
    icon: 'Music',
  },
  {
    type: 'conditional',
    label: 'Conditional',
    description: 'Branch based on condition',
    color: '#faad14',
    icon: 'GitBranch',
  },
  {
    type: 'javascript',
    label: 'JavaScript',
    description: 'Execute JavaScript code',
    color: '#f5222d',
    icon: 'Code',
  },
  {
    type: 'prompt',
    label: 'Prompt',
    description: 'Input text or prompt',
    color: '#a0d911',
    icon: 'FileText',
  },
  {
    type: 'tool',
    label: 'Tool',
    description: 'Custom tool',
    color: '#2f54eb',
    icon: 'Wrench',
  },
  {
    type: 'structuredOutput',
    label: 'Structured Output',
    description: 'Parse structured data',
    color: '#52c41a',
    icon: 'Database',
  },
  {
    type: 'database',
    label: 'Database',
    description: 'Execute SQL queries',
    color: '#1890ff',
    icon: 'Database',
  },
  {
    type: 'file',
    label: 'File',
    description: 'File operations (read/write)',
    color: '#722ed1',
    icon: 'File',
  },
  {
    type: 'notification',
    label: 'Notification',
    description: 'Send notifications (webhook/email)',
    color: '#fa8c16',
    icon: 'Bell',
  },
  {
    type: 'loop',
    label: 'Loop',
    description: 'Iterate over arrays or ranges',
    color: '#1890ff',
    icon: 'Repeat',
  },
];
