/**
 * Tool Node - 自定义工具节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { ToolOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface ToolNodeData {
  tool_id?: string;
  toolId?: string; // legacy key (will be normalized server-side)
  name?: string;
  description?: string;
  code?: string; // legacy inline tool code (kept for backward compatibility display)
  status?: NodeStatus;
  output?: unknown;
}

function ToolNode({ data, selected }: NodeProps<ToolNodeData>) {
  const status = data.status || 'idle';
  const toolId = data.tool_id || data.toolId || '';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeTool}`}>
          <ToolOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>
            {data.name || toolId || 'Tool'}
          </h3>
          <p className={styles.nodeDescription}>
            {data.description || (toolId ? 'Tool reference' : 'Select a tool')}
          </p>
        </div>
      </div>

      <div className={styles.nodeContent}>
        <div className={styles.nodeField}>
          <span className={styles.nodeFieldLabel}>Tool ID:</span>
          <div className={styles.nodeCodeBlock}>{toolId || '(missing)'}</div>
        </div>

        {data.code ? (
          <div className={styles.nodeField}>
            <span className={styles.nodeFieldLabel}>Legacy Code:</span>
            <div className={styles.nodeCodeBlock}>{data.code}</div>
          </div>
        ) : null}

        {status === 'running' && (
          <div className={`${styles.nodeStatus} ${styles.nodeStatusRunning}`} style={{ padding: 0 }}>
            <LoadingOutlined spin />
            Executing tool...
          </div>
        )}
      </div>

      {data.output && (
        <div className={styles.nodeOutput}>
          <p className={styles.nodeOutputLabel}>
            Output:
          </p>
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
        style={{ backgroundColor: 'var(--color-accent-tool)' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: 'var(--color-accent-tool)' }}
      />
    </Card>
  );
}

export default memo(ToolNode);
