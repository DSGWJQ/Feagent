/**
 * End Node - 工作流结束节点
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { CheckCircleOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

export interface EndNodeData {
  status?: NodeStatus;
  output?: any;
}

function EndNode({ data, selected }: NodeProps<EndNodeData>) {
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
            backgroundColor: '#ff4d4f',
            color: '#fff',
          }}
        >
          <CheckCircleOutlined style={{ fontSize: 16 }} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>End</h3>
          <p style={{ margin: 0, fontSize: 12, color: '#8c8c8c' }}>
            Workflow exit point
          </p>
        </div>
      </div>

      {status === 'completed' && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 16px',
            fontSize: 12,
            color: '#52c41a',
          }}
        >
          <CheckCircleOutlined />
          Completed
        </div>
      )}

      {data.output && (
        <div
          style={{
            padding: 12,
            borderTop: '1px solid #f0f0f0',
            backgroundColor: '#fafafa',
          }}
        >
          <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 500 }}>
            Final Output:
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
              {typeof data.output === 'string'
                ? data.output
                : JSON.stringify(data.output, null, 2)}
            </pre>
          </div>
        </div>
      )}

      <Handle
        type="target"
        position={Position.Left}
        id="input"
        style={{ backgroundColor: '#ff4d4f' }}
      />
    </Card>
  );
}

export default memo(EndNode);
