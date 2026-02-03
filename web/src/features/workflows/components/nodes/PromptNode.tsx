/**
 * Prompt Node - 提示词节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface PromptNodeData extends Record<string, unknown> {
  content: string;
  status?: NodeStatus;
  output?: unknown;
}

type PromptNodeType = Node<PromptNodeData>;

function PromptNode({ data, selected }: NodeProps<PromptNodeType>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypePrompt}`}>
          <FileTextOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>Prompt</h3>
          <p className={styles.nodeDescription}>
            Input text or prompt
          </p>
        </div>
      </div>

      <div className={styles.nodeContent}>
        <div className={styles.nodeCodeBlock}>
          {data.content || 'Enter your prompt...'}
        </div>
      </div>

      <Handle
        type="target"
        position={Position.Left}
        id="input"
        style={{ backgroundColor: 'var(--color-primary-500)' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: 'var(--color-primary-500)' }}
      />
    </Card>
  );
}

export default memo(PromptNode);
