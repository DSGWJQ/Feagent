/**
 * Notification Node - 通知节点
 *
 * 功能：
 * - 发送 Webhook 通知
 * - 发送邮件通知
 * - 发送 Slack 通知
 * - 支持包含输入数据
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, Input } from 'antd';
import { BellOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

const { TextArea } = Input;

export interface NotificationNodeData {
  type: 'webhook' | 'email' | 'slack';
  subject: string;
  message: string;
  url: string;
  include_input: boolean;
  status?: NodeStatus;
  output?: any;
}

function NotificationNode({ data, selected, id }: NodeProps<NotificationNodeData>) {
  const status = data.status || 'idle';

  return (
    <>
      {/* 输入连接点 */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: '#1890ff',
          width: 12,
          height: 12,
        }}
      />

      <Card
        className={`workflow-node ${getStatusColor(status, selected)} ${selected ? 'selected' : ''} ${status === 'running' ? 'node-running' : ''}`}
        style={{
          minWidth: 320,
          maxWidth: 450,
          border: '2px solid',
          borderColor: selected ? '#1890ff' : '#d9d9d9',
          transition: 'all 0.3s',
          boxShadow: selected
            ? '0 4px 12px rgba(24, 144, 255, 0.3)'
            : '0 2px 8px rgba(0, 0, 0, 0.1)',
        }}
        styles={{ body: { padding: 0 } }}
      >
        {/* 节点头部 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '12px 16px',
            borderBottom: '1px solid #f0f0f0',
            backgroundColor: '#fafafa',
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
            {status === 'running' ? (
              <LoadingOutlined style={{ fontSize: 16 }} spin />
            ) : (
              <BellOutlined style={{ fontSize: 16 }} role="img" />
            )}
          </div>
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
              通知
            </h3>
          </div>
        </div>

        {/* 节点内容 */}
        <div style={{ padding: '16px' }}>
          {/* 通知类型 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              通知类型
            </label>
            <Input
              placeholder="webhook / email / slack"
              value={data.type}
              readOnly
              style={{
                fontSize: 12,
                backgroundColor: '#f5f5f5',
              }}
            />
          </div>

          {/* 主题 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              主题
            </label>
            <Input
              placeholder="通知主题"
              value={data.subject}
              readOnly
              style={{
                fontSize: 12,
                backgroundColor: '#f5f5f5',
              }}
            />
          </div>

          {/* 消息 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              消息
            </label>
            <TextArea
              placeholder="通知消息内容"
              value={data.message}
              readOnly
              rows={3}
              style={{
                fontSize: 12,
                backgroundColor: '#f5f5f5',
              }}
            />
          </div>

          {/* Webhook URL（仅在 webhook 类型时显示） */}
          {data.type === 'webhook' && (
            <div style={{ marginBottom: 12 }}>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  color: '#8c8c8c',
                  marginBottom: 4,
                }}
              >
                Webhook URL
              </label>
              <Input
                placeholder="https://webhook.example.com"
                value={data.url}
                readOnly
                style={{
                  fontSize: 12,
                  backgroundColor: '#f5f5f5',
                }}
              />
            </div>
          )}

          {/* 包含输入数据 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              包含输入数据
            </label>
            <div
              style={{
                fontSize: 12,
                padding: '4px 11px',
                backgroundColor: '#f5f5f5',
                borderRadius: 4,
                color: data.include_input ? '#52c41a' : '#8c8c8c',
              }}
            >
              {data.include_input ? '是' : '否'}
            </div>
          </div>

          {/* 执行结果 */}
          {data.output && (
            <div style={{ marginTop: 12 }}>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  color: '#52c41a',
                  marginBottom: 4,
                }}
              >
                执行结果
              </label>
              <pre
                style={{
                  margin: 0,
                  padding: 8,
                  backgroundColor: '#f6ffed',
                  border: '1px solid #b7eb8f',
                  borderRadius: 4,
                  fontSize: 11,
                  maxHeight: 100,
                  overflow: 'auto',
                }}
              >
                {typeof data.output === 'string'
                  ? data.output
                  : JSON.stringify(data.output, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </Card>

      {/* 输出连接点 */}
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: '#52c41a',
          width: 12,
          height: 12,
        }}
      />
    </>
  );
}

export default memo(NotificationNode);
