/**
 * Image Generation Node - 图像生成节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { PictureOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface ImageGenerationNodeData extends Record<string, unknown> {
  model: string;
  aspectRatio: string;
  outputFormat: string;
  prompt?: string;
  status?: NodeStatus;
  output?: unknown;
}

type ImageGenerationNodeType = Node<ImageGenerationNodeData>;

function ImageGenerationNode({
  data,
  selected,
}: NodeProps<ImageGenerationNodeType>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeImage}`}>
          <PictureOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>
            Image Generation
          </h3>
          <p className={styles.nodeDescription}>
            {data.model || 'gemini-2.5-flash-image'}
          </p>
        </div>
      </div>

      <div className={styles.nodeContent} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>Aspect Ratio:</span>
          <Tag color="blue" style={{ margin: 0 }}>
            {data.aspectRatio || '1:1'}
          </Tag>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>Format:</span>
          <Tag color="green" style={{ margin: 0 }}>
            {data.outputFormat || 'png'}
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
            Generating image...
          </div>
        )}
      </div>

      {data.output != null && (
        <div className={styles.nodeOutput}>
          <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 500 }}>
            Generated Image:
          </p>
          {typeof data.output === 'string' && data.output.startsWith('http') ? (
            <img
              src={data.output}
              alt="Generated"
              style={{ width: '100%', borderRadius: 4 }}
            />
          ) : (
            <div
              style={{
                padding: 8,
                backgroundColor: '#fff',
                borderRadius: 4,
                fontSize: 12,
              }}
            >
              {JSON.stringify(data.output, null, 2)}
            </div>
          )}
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

export default memo(ImageGenerationNode);
