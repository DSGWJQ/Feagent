/**
 * Text Model Node - LLM 文本生成节点
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { MessageOutlined, LoadingOutlined, SettingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

export interface TextModelNodeData {
  model: string;
  temperature: number;
  maxTokens: number;
  prompt?: string;
  status?: NodeStatus;
  structuredOutput?: boolean;
  schema?: string;
  schemaName?: string;
  output?: any;
}

function TextModelNode({ data, selected }: NodeProps<TextModelNodeData>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)}`}
      style={{
        minWidth: 280,
        maxWidth: 400,
        border: '2px solid',
        transition: 'all 0.3s',
      }}
      bodyStyle={{ padding: 0 }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 16px',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 6,
            backgroundColor: '#722ed1',
            color: '#fff',
          }}
        >
          <MessageOutlined style={{ fontSize: 16 }} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
            Text Model
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#8c8c8c' }}>
            {data.model || 'openai/gpt-5'}
          </p>
        </div>
        <SettingOutlined style={{ fontSize: 14, color: '#8c8c8c' }} />
      </div>

      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>Temperature:</span>
          <span style={{ fontFamily: 'monospace' }}>{data.temperature || 0.7}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>Max Tokens:</span>
          <span style={{ fontFamily: 'monospace' }}>{data.maxTokens || 2000}</span>
        </div>
        {data.structuredOutput && (
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span style={{ color: '#8c8c8c' }}>Structured:</span>
            <Tag color="blue" style={{ margin: 0 }}>
              {data.schemaName || 'Yes'}
            </Tag>
          </div>
        )}

        {status === 'running' && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              color: '#faad14',
              marginTop: 4,
            }}
          >
            <LoadingOutlined spin />
            Generating...
          </div>
        )}
      </div>

      {data.output && (
        <div
          style={{
            padding: 12,
            borderTop: '1px solid #f0f0f0',
            backgroundColor: '#fafafa',
          }}
        >
          <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 500 }}>
            Output:
          </p>
          <div
            style={{
              padding: 8,
              backgroundColor: '#fff',
              borderRadius: 4,
              maxHeight: 128,
              overflow: 'auto',
            }}
          >
            <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
              {typeof data.output === 'object' && data.output.text
                ? data.output.text
                : typeof data.output === 'string'
                  ? data.output
                  : JSON.stringify(data.output, null, 2)}
            </pre>
          </div>
        </div>
      )}

      <Handle
        type="target"
        position={Position.Left}
        id="prompt"
        style={{ backgroundColor: '#722ed1' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: '#722ed1' }}
      />
    </Card>
  );
}

export default memo(TextModelNode);

