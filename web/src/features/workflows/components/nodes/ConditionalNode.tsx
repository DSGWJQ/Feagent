/**
 * Conditional Node - 条件分支节点
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { BranchesOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

export interface ConditionalNodeData {
  condition: string;
  status?: NodeStatus;
  output?: any;
}

function ConditionalNode({ data, selected }: NodeProps<ConditionalNodeData>) {
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
            backgroundColor: '#faad14',
            color: '#fff',
          }}
        >
          <BranchesOutlined style={{ fontSize: 16 }} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
            Conditional
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#8c8c8c' }}>
            Branch based on condition
          </p>
        </div>
      </div>

      <div style={{ padding: 16 }}>
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: '#8c8c8c' }}>Condition:</span>
          <div
            style={{
              marginTop: 4,
              padding: 8,
              backgroundColor: '#fafafa',
              borderRadius: 4,
              fontSize: 12,
              fontFamily: 'monospace',
            }}
          >
            {data.condition || "input1 === 'value'"}
          </div>
        </div>

        {status === 'running' && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              color: '#faad14',
            }}
          >
            <LoadingOutlined spin />
            Evaluating...
          </div>
        )}
      </div>

      <Handle
        type="target"
        position={Position.Left}
        id="input"
        style={{ backgroundColor: '#faad14' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        style={{ backgroundColor: '#52c41a', top: '40%' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        style={{ backgroundColor: '#ff4d4f', top: '60%' }}
      />
    </Card>
  );
}

export default memo(ConditionalNode);

