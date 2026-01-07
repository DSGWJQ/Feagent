/**
 * End Node - 工作流结束节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { CheckCircleOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface EndNodeData {
  status?: NodeStatus;
  output?: any;
}

function EndNode({ data, selected }: NodeProps<EndNodeData>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCard}`}
      styles={{ body: { padding: 0 } }}
      data-testid="workflow-node-end"
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeEnd}`}>
          <CheckCircleOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>End</h3>
          <p className={styles.nodeDescriptionNoMargin}>
            Workflow exit point
          </p>
        </div>
      </div>

      {status === 'completed' && (
        <div className={`${styles.nodeStatus} ${styles.nodeStatusCompleted}`}>
          <CheckCircleOutlined />
          Completed
        </div>
      )}

      {data.output && (
        <div className={styles.nodeOutput}>
          <p className={styles.nodeOutputLabel}>
            Final Output:
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
        style={{ backgroundColor: 'var(--color-error)' }}
      />
    </Card>
  );
}

export default memo(EndNode);
