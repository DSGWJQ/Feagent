/**
 * Audio Node - 音频生成节点
 * 使用CSS Module + 设计Token系统
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { SoundOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

export interface AudioNodeData {
  model: string;
  voice: string;
  speed: number;
  text?: string;
  status?: NodeStatus;
  output?: any;
}

function AudioNode({ data, selected }: NodeProps<AudioNodeData>) {
  const status = data.status || 'idle';

  return (
    <Card
      className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
      styles={{ body: { padding: 0 } }}
    >
      <div className={styles.nodeHeaderWrapper}>
        <div className={`${styles.nodeIcon} ${styles.nodeTypeAudio}`}>
          <SoundOutlined style={{ fontSize: 16 }} />
        </div>
        <div className={styles.nodeTitleWrapper}>
          <h3 className={styles.nodeTitle}>Audio</h3>
          <p className={styles.nodeDescription}>
            {data.model || 'openai/tts-1'}
          </p>
        </div>
      </div>

      <div className={styles.nodeContent} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>Voice:</span>
          <Tag color="purple" style={{ margin: 0 }}>
            {data.voice || 'alloy'}
          </Tag>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>Speed:</span>
          <span style={{ fontFamily: 'monospace' }}>{data.speed || 1.0}x</span>
        </div>

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
            Generating audio...
          </div>
        )}
      </div>

      {data.output && (
        <div className={styles.nodeOutput}>
          <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 500 }}>
            Generated Audio:
          </p>
          {typeof data.output === 'string' && data.output.startsWith('http') ? (
            <audio controls style={{ width: '100%' }}>
              <source src={data.output} type="audio/mpeg" />
            </audio>
          ) : (
            <div
              style={{
                padding: 8,
                backgroundColor: '#fff',
                borderRadius: 4,
                fontSize: 12,
              }}
            >
              {JSON.stringify(data.output, null, 2)}
            </div>
          )}
        </div>
      )}

      <Handle
        type="target"
        position={Position.Left}
        id="text"
        style={{ backgroundColor: '#eb2f96' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: '#eb2f96' }}
      />
    </Card>
  );
}

export default memo(AudioNode);
