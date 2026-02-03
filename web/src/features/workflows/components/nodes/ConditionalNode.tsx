/**
 * Conditional Node - 条件分支节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { BranchesOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface ConditionalNodeData extends Record<string, unknown> {
  condition: string;
  status?: NodeStatus;
  output?: unknown;
}

type ConditionalNodeType = Node<ConditionalNodeData>;

function ConditionalNode({ data, selected }: NodeProps<ConditionalNodeType>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeConditional}`}>
          <BranchesOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>Conditional</h3>
          <p className={styles.nodeDescription}>
            Branch based on condition
          </p>
        </div>
      </div>

      <div className={styles.nodeContent}>
        <div className={styles.nodeField}>
          <span className={styles.nodeFieldLabel}>Condition:</span>
          <div className={styles.nodeCodeBlock}>
            {data.condition || 'if (value > 10) return true;'}
          </div>
        </div>

        {status === 'running' && (
          <div className={`${styles.nodeStatus} ${styles.nodeStatusRunning}`} style={{ padding: 0 }}>
            <LoadingOutlined spin />
            Evaluating condition...
          </div>
        )}
      </div>

      <Handle
        type="target"
        position={Position.Left}
        id="input"
        style={{ backgroundColor: 'var(--color-warning)' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        style={{ top: '40%', backgroundColor: 'var(--color-success)' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        style={{ top: '60%', backgroundColor: 'var(--color-error)' }}
      />
    </Card>
  );
}

export default memo(ConditionalNode);
