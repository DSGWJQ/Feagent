/**
 * HTTP Request Node - HTTP 请求节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { GlobalOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface HttpRequestNodeData extends Record<string, unknown> {
  url: string;
  method: string;
  headers?: string;
  body?: string;
  status?: NodeStatus;
  output?: unknown;
}

type HttpRequestNodeType = Node<HttpRequestNodeData>;

function HttpRequestNode({ data, selected, id }: NodeProps<HttpRequestNodeType>) {
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
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
      data-testid={`workflow-node-${id}`}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeHttp}`}>
          <GlobalOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>
            HTTP Request{' '}
            <Tag color={getMethodColor(data.method || 'GET')} style={{ fontSize: 10 }}>
              {(data.method || 'GET').toUpperCase()}
            </Tag>
          </h3>
          <p className={styles.nodeDescription}>
            {data.url || 'Configure URL'}
          </p>
        </div>
      </div>

      <div className={styles.nodeContent}>
        {status === 'running' && (
          <div className={`${styles.nodeStatus} ${styles.nodeStatusRunning}`} style={{ padding: 0 }}>
            <LoadingOutlined spin />
            Sending request...
          </div>
        )}
      </div>

      {data.output != null && (
        <div className={styles.nodeOutput}>
          <p className={styles.nodeOutputLabel}>Response:</p>
          <div className={styles.nodeOutputContent}>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
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
        style={{ backgroundColor: 'var(--color-info)' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: 'var(--color-info)' }}
      />
    </Card>
  );
}

export default memo(HttpRequestNode);
