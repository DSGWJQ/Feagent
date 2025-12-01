/**
 * Audio Node - 音频生成节点
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { SoundOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

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
      className={`workflow-node ${getStatusColor(status, selected)}`}
      style={{
        minWidth: 280,
        maxWidth: 400,
        border: '2px solid',
        transition: 'all 0.3s',
      }}
      styles={{ body: { padding: 0 } }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 16px',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 6,
            backgroundColor: '#eb2f96',
            color: '#fff',
          }}
        >
          <SoundOutlined style={{ fontSize: 16 }} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Audio</h3>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#8c8c8c' }}>
            {data.model || 'openai/tts-1'}
          </p>
        </div>
      </div>

      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
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
        <div
          style={{
            padding: 12,
            borderTop: '1px solid #f0f0f0',
            backgroundColor: '#fafafa',
          }}
        >
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
