/**
 * Prompt Node - 提示词节点
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

export interface PromptNodeData {
  content: string;
  status?: NodeStatus;
  output?: any;
}

function PromptNode({ data, selected }: NodeProps<PromptNodeData>) {
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
            backgroundColor: '#a0d911',
            color: '#fff',
          }}
        >
          <FileTextOutlined style={{ fontSize: 16 }} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Prompt</h3>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#8c8c8c' }}>
            Input text or prompt
          </p>
        </div>
      </div>

      <div style={{ padding: 16 }}>
        <div
          style={{
            padding: 8,
            backgroundColor: '#fafafa',
            borderRadius: 4,
            fontSize: 12,
            maxHeight: 100,
            overflow: 'auto',
          }}
        >
          {data.content || 'Enter your prompt...'}
        </div>
      </div>

      <Handle
        type="target"
        position={Position.Left}
        id="input"
        style={{ backgroundColor: '#a0d911' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: '#a0d911' }}
      />
    </Card>
  );
}

export default memo(PromptNode);

