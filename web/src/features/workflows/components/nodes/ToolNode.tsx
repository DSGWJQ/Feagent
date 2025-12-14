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
  name: string;
  description: string;
  code: string;
  status?: NodeStatus;
  output?: any;
}

function ToolNode({ data, selected }: NodeProps<ToolNodeData>) {
  const status = data.status || 'idle';

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
            {data.name || 'Tool'}
          </h3>
          <p className={styles.nodeDescription}>
            {data.description || 'Custom tool'}
          </p>
        </div>
      </div>

      <div className={styles.nodeContent}>
        <div className={styles.nodeField}>
          <span className={styles.nodeFieldLabel}>Code:</span>
          <div className={styles.nodeCodeBlock}>
            {data.code || 'async function execute(args) {\n  return result;\n}'}
          </div>
        </div>

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
