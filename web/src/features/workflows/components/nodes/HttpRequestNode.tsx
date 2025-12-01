/**
 * HTTP Request Node - HTTP 请求节点
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { GlobalOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

export interface HttpRequestNodeData {
  url: string;
  method: string;
  headers?: string;
  body?: string;
  status?: NodeStatus;
  output?: any;
}

function HttpRequestNode({ data, selected }: NodeProps<HttpRequestNodeData>) {
  const status = data.status || 'idle';

  const getMethodColor = (method: string) => {
    switch (method.toUpperCase()) {
      case 'GET':
        return 'blue';
      case 'POST':
        return 'green';
      case 'PUT':
        return 'orange';
      case 'DELETE':
        return 'red';
      case 'PATCH':
        return 'purple';
      default:
        return 'default';
    }
  };

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
            backgroundColor: '#1890ff',
            color: '#fff',
          }}
        >
          <GlobalOutlined style={{ fontSize: 16 }} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
            HTTP Request
          </h3>
          <Tag color={getMethodColor(data.method || 'GET')} style={{ margin: '4px 0 0' }}>
            {data.method || 'GET'}
          </Tag>
        </div>
      </div>

      <div style={{ padding: 16 }}>
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: '#8c8c8c' }}>URL:</span>
          <div
            style={{
              marginTop: 4,
              padding: 8,
              backgroundColor: '#fafafa',
              borderRadius: 4,
              fontSize: 12,
              fontFamily: 'monospace',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {data.url || 'https://api.example.com'}
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
            Requesting...
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
            Response:
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
        style={{ backgroundColor: '#1890ff' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: '#1890ff' }}
      />
    </Card>
  );
}

export default memo(HttpRequestNode);
