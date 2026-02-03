/**
 * Structured Output Node - 结构化输出节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { DatabaseOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface StructuredOutputNodeData extends Record<string, unknown> {
  schemaName: string;
  mode: string;
  schema?: string;
  status?: NodeStatus;
  output?: unknown;
}

type StructuredOutputNodeType = Node<StructuredOutputNodeData>;

function StructuredOutputNode({
  data,
  selected,
}: NodeProps<StructuredOutputNodeType>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeStructuredOutput}`}>
          <DatabaseOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>
            Structured Output
          </h3>
          <p className={styles.nodeDescription}>
            {data.schemaName || 'MySchema'}
          </p>
        </div>
      </div>

      <div className={styles.nodeContent} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>Mode:</span>
          <Tag color="green" style={{ margin: 0 }}>
            {data.mode || 'object'}
          </Tag>
        </div>

        {data.schema && (
          <div style={{ marginTop: 4 }}>
            <span style={{ fontSize: 12, color: '#8c8c8c' }}>Schema:</span>
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
              {data.schema}
            </div>
          </div>
        )}

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
            Parsing...
          </div>
        )}
      </div>

      {data.output != null && (
        <div className={styles.nodeOutput}>
          <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 500 }}>
            Parsed Output:
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
        style={{ backgroundColor: 'var(--color-accent-workflow)' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: 'var(--color-accent-workflow)' }}
      />
    </Card>
  );
}

export default memo(StructuredOutputNode);
