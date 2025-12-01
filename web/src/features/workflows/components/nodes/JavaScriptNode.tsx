/**
 * JavaScript Node - JavaScript 代码执行节点
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { CodeOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

export interface JavaScriptNodeData {
  code: string;
  status?: NodeStatus;
  output?: any;
}

function JavaScriptNode({ data, selected }: NodeProps<JavaScriptNodeData>) {
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
            backgroundColor: '#f5222d',
            color: '#fff',
          }}
        >
          <CodeOutlined style={{ fontSize: 16 }} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
            JavaScript
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#8c8c8c' }}>
            Execute JavaScript code
          </p>
        </div>
      </div>

      <div style={{ padding: 16 }}>
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: '#8c8c8c' }}>Code:</span>
          <div
            style={{
              marginTop: 4,
              padding: 8,
              backgroundColor: '#fafafa',
              borderRadius: 4,
              fontSize: 11,
              fontFamily: 'monospace',
              maxHeight: 100,
              overflow: 'auto',
            }}
          >
            {data.code || '// Your code here\nreturn input1;'}
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
            Executing...
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
        style={{ backgroundColor: '#f5222d' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: '#f5222d' }}
      />
    </Card>
  );
}

export default memo(JavaScriptNode);
