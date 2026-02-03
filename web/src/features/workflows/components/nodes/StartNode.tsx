/**
 * Start Node - 工作流开始节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface StartNodeData extends Record<string, unknown> {
  status?: NodeStatus;
  output?: unknown;
}

type StartNodeType = Node<StartNodeData>;

function StartNode({ data, selected }: NodeProps<StartNodeType>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCard}`}
      styles={{ body: { padding: 0 } }}
      data-testid="workflow-node-start"
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeStart}`}>
          <PlayCircleOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>Start</h3>
          <p className={styles.nodeDescriptionNoMargin}>
            Workflow entry point
          </p>
        </div>
      </div>

      {status === 'running' && (
        <div className={`${styles.nodeStatus} ${styles.nodeStatusRunning}`}>
          <div className={`${styles.statusPulse} ${styles.statusPulseRunning}`} />
          Starting...
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: 'var(--color-success)' }}
      />
    </Card>
  );
}

export default memo(StartNode);
