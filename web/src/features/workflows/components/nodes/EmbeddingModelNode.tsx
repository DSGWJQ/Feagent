/**
 * Embedding Model Node - 向量嵌入节点
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { ApartmentOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

export interface EmbeddingModelNodeData {
  model: string;
  dimensions: number;
  text?: string;
  status?: NodeStatus;
  output?: any;
}

function EmbeddingModelNode({
  data,
  selected,
}: NodeProps<EmbeddingModelNodeData>) {
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
            backgroundColor: '#13c2c2',
            color: '#fff',
          }}
        >
          <ApartmentOutlined style={{ fontSize: 16 }} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
            Embedding Model
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#8c8c8c' }}>
            {data.model || 'openai/text-embedding-3-small'}
          </p>
        </div>
      </div>

      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>Dimensions:</span>
          <Tag color="cyan" style={{ margin: 0 }}>
            {data.dimensions || 1536}
          </Tag>
        </div>

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
            Generating embeddings...
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
            Embedding Vector:
          </p>
          <div
            style={{
              padding: 8,
              backgroundColor: '#fff',
              borderRadius: 4,
              fontSize: 12,
            }}
          >
            {Array.isArray(data.output)
              ? `[${data.output.slice(0, 5).join(', ')}... (${data.output.length} dimensions)]`
              : JSON.stringify(data.output, null, 2)}
          </div>
        </div>
      )}

      <Handle
        type="target"
        position={Position.Left}
        id="text"
        style={{ backgroundColor: '#13c2c2' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: '#13c2c2' }}
      />
    </Card>
  );
}

export default memo(EmbeddingModelNode);
