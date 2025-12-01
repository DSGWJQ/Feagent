/**
 * Start Node - 工作流开始节点
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

export interface StartNodeData {
  status?: NodeStatus;
  output?: any;
}

function StartNode({ data, selected }: NodeProps<StartNodeData>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)}`}
      style={{
        minWidth: 200,
        border: '2px solid',
        transition: 'all 0.3s',
      }}
      styles={{ body: { padding: 0 } }}
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
            backgroundColor: '#52c41a',
            color: '#fff',
          }}
        >
          <PlayCircleOutlined style={{ fontSize: 16 }} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Start</h3>
          <p style={{ margin: 0, fontSize: 12, color: '#8c8c8c' }}>
            Workflow entry point
          </p>
        </div>
      </div>

      {status === 'running' && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 16px',
            fontSize: 12,
            color: '#faad14',
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: '#faad14',
              animation: 'pulse 1.5s ease-in-out infinite',
            }}
          />
          Starting...
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: '#52c41a' }}
      />
    </Card>
  );
}

export default memo(StartNode);
