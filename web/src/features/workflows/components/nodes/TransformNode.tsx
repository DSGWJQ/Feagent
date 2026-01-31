/**
 * Transform Node - 数据转换节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { SwapOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface TransformNodeData {
  type: string;
  mapping?: Record<string, unknown>;
  conversions?: Record<string, unknown>;
  path?: string;
  fields?: unknown;
  field?: string;
  condition?: string;
  operations?: unknown;
  aggregation?: Record<string, unknown>;
  function?: string;
  element_transform?: Record<string, unknown>;
  status?: NodeStatus;
  output?: unknown;
}

function TransformNode({ id, data, selected }: NodeProps<TransformNodeData>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
      data-testid={`workflow-node-${id}`}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeConditional}`}>
          {status === 'running' ? (
            <LoadingOutlined style={{ fontSize: 16 }} spin />
          ) : (
            <SwapOutlined style={{ fontSize: 16 }} role="img" />
          )}
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>Transform</h3>
          <p className={styles.nodeDescription}>Data mapping / cleaning</p>
        </div>
      </div>

      <div className={styles.nodeContent}>
        <div style={{ marginBottom: 8, fontSize: 12, color: '#8c8c8c' }}>
          Type: <span style={{ color: '#fff' }}>{data.type || '(unset)'}</span>
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
            Transforming...
          </div>
        )}
      </div>

      {data.output && (
        <div className={styles.nodeOutput}>
          <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 500 }}>Output:</p>
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
              {typeof data.output === 'string' ? data.output : JSON.stringify(data.output, null, 2)}
            </pre>
          </div>
        </div>
      )}

      <Handle type="target" position={Position.Left} id="input" style={{ backgroundColor: '#faad14' }} />
      <Handle type="source" position={Position.Right} id="output" style={{ backgroundColor: '#faad14' }} />
    </Card>
  );
}

export default memo(TransformNode);
