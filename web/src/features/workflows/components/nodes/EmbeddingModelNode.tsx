/**
 * Embedding Model Node - 向量嵌入节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { ApartmentOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface EmbeddingModelNodeData extends Record<string, unknown> {
  model: string;
  dimensions: number;
  text?: string;
  status?: NodeStatus;
  output?: unknown;
}

type EmbeddingModelNodeType = Node<EmbeddingModelNodeData>;

function EmbeddingModelNode({
  data,
  selected,
}: NodeProps<EmbeddingModelNodeType>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeEmbedding}`}>
          <ApartmentOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>
            Embedding Model
          </h3>
          <p className={styles.nodeDescription}>
            {data.model || 'openai/text-embedding-3-small'}
          </p>
        </div>
      </div>

      <div className={styles.nodeContent} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
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

      {data.output != null && (
        <div className={styles.nodeOutput}>
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
