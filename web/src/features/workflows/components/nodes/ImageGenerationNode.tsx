/**
 * Image Generation Node - 图像生成节点
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, Tag } from 'antd';
import { PictureOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

export interface ImageGenerationNodeData {
  model: string;
  aspectRatio: string;
  outputFormat: string;
  prompt?: string;
  status?: NodeStatus;
  output?: any;
}

function ImageGenerationNode({
  data,
  selected,
}: NodeProps<ImageGenerationNodeData>) {
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
      bodyStyle={{ padding: 0 }}
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
            backgroundColor: '#fa8c16',
            color: '#fff',
          }}
        >
          <PictureOutlined style={{ fontSize: 16 }} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
            Image Generation
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#8c8c8c' }}>
            {data.model || 'gemini-2.5-flash-image'}
          </p>
        </div>
      </div>

      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>Aspect Ratio:</span>
          <Tag color="blue" style={{ margin: 0 }}>
            {data.aspectRatio || '1:1'}
          </Tag>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>Format:</span>
          <Tag color="green" style={{ margin: 0 }}>
            {data.outputFormat || 'png'}
          </Tag>
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
            Generating image...
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
            Generated Image:
          </p>
          {typeof data.output === 'string' && data.output.startsWith('http') ? (
            <img
              src={data.output}
              alt="Generated"
              style={{ width: '100%', borderRadius: 4 }}
            />
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
        id="prompt"
        style={{ backgroundColor: '#fa8c16' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        style={{ backgroundColor: '#fa8c16' }}
      />
    </Card>
  );
}

export default memo(ImageGenerationNode);

