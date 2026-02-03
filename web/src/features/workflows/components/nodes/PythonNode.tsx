/**
 * Python Node - Python 代码执行节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { CodeOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface PythonNodeData extends Record<string, unknown> {
  code: string;
  status?: NodeStatus;
  output?: unknown;
}

type PythonNodeType = Node<PythonNodeData>;

function PythonNode({ id, data, selected }: NodeProps<PythonNodeType>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
      data-testid={`workflow-node-${id}`}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeJavaScript}`}>
          {status === 'running' ? (
            <LoadingOutlined style={{ fontSize: 16 }} spin />
          ) : (
            <CodeOutlined style={{ fontSize: 16 }} role="img" />
          )}
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>Python</h3>
          <p className={styles.nodeDescription}>Execute Python code</p>
        </div>
      </div>

      <div className={styles.nodeContent}>
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
            {data.code || 'result = input1'}
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

      {data.output != null && (
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

export default memo(PythonNode);
