/**
 * Text Model Node - LLM 文本生成节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { MessageOutlined, LoadingOutlined, SettingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface TextModelNodeData extends Record<string, unknown> {
  model: string;
  temperature: number;
  maxTokens: number;
  prompt?: string;
  status?: NodeStatus;
  structuredOutput?: boolean;
  schema?: string;
  schemaName?: string;
  output?: unknown;
}

type TextModelNodeType = Node<TextModelNodeData>;

function TextModelNode({ data, selected, id }: NodeProps<TextModelNodeType>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
      data-testid={`workflow-node-${id}`}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeTextModel}`}>
          <MessageOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>Text Model</h3>
          <p className={styles.nodeDescription}>
            {data.model || 'openai/gpt-5'}
          </p>
        </div>
        <SettingOutlined style={{ fontSize: 14, color: 'var(--color-neutral-500)' }} />
      </div>

      <div className={styles.nodeContent} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span className={styles.nodeFieldLabel}>Temperature:</span>
          <span style={{ fontFamily: 'var(--font-family-code)' }}>{data.temperature || 0.7}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span className={styles.nodeFieldLabel}>Max Tokens:</span>
          <span style={{ fontFamily: 'var(--font-family-code)' }}>{data.maxTokens || 2000}</span>
        </div>
        {data.structuredOutput && (
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span className={styles.nodeFieldLabel}>Structured:</span>
            <Tag color="blue" style={{ margin: 0 }}>
              {data.schemaName || 'Yes'}
            </Tag>
          </div>
        )}

        {status === 'running' && (
          <div className={`${styles.nodeStatus} ${styles.nodeStatusRunning}`} style={{ padding: 0, marginTop: 4 }}>
            <LoadingOutlined spin />
            Generating...
          </div>
        )}
      </div>

      {data.output != null && (
        <div className={styles.nodeOutput}>
          <p className={styles.nodeOutputLabel}>Output:</p>
          <div className={styles.nodeOutputContent}>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
              {(() => {
                if (typeof data.output === 'string') {
                  return data.output;
                }
                if (
                  data.output &&
                  typeof data.output === 'object' &&
                  'text' in data.output &&
                  typeof (data.output as { text?: unknown }).text === 'string'
                ) {
                  return (data.output as { text: string }).text;
                }
                return JSON.stringify(data.output, null, 2);
              })()}
            </pre>
          </div>
        </div>
      )}

      <Handle
        type="target"
        position={Position.Left}
        id="prompt"
        style={{ backgroundColor: 'var(--color-primary-400)' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: 'var(--color-primary-400)' }}
      />
    </Card>
  );
}

export default memo(TextModelNode);
