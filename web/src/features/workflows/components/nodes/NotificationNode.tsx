/**
 * Notification Node - 通知节点
 * 使用CSS Module + 设计Token系统
 *
 * 功能：
 * - 发送 Webhook 通知
 * - 发送邮件通知
 * - 发送 Slack 通知
 * - 支持包含输入数据
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card, Input } from 'antd';
import { BellOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

const { TextArea } = Input;

export interface NotificationNodeData extends Record<string, unknown> {
  type: 'webhook' | 'email' | 'slack';
  subject: string;
  message: string;
  url: string;
  include_input: boolean;
  status?: NodeStatus;
  output?: unknown;
}

type NotificationNodeType = Node<NotificationNodeData>;

function NotificationNode({ data, selected, id }: NodeProps<NotificationNodeType>) {
  const status = data.status || 'idle';

  return (
    <>
      {/* 输入连接点 */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: '#eb2f96',
          width: 12,
          height: 12,
        }}
      />

      <Card
        className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
        styles={{ body: { padding: 0 } }}
        data-testid={`workflow-node-${id}`}
      >
        {/* 节点头部 */}
        <div className={styles.nodeHeaderWrapper}>
          <div className={`${styles.nodeIcon} ${styles.nodeTypeNotification}`}>
            {status === 'running' ? (
              <LoadingOutlined style={{ fontSize: 16 }} spin />
            ) : (
              <BellOutlined style={{ fontSize: 16 }} role="img" />
            )}
          </div>
          <div className={styles.nodeTitleWrapper}>
            <h3 className={styles.nodeTitle}>
              通知
            </h3>
          </div>
        </div>

        {/* 节点内容 */}
        <div className={styles.nodeContent}>
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
        </div>

        {/* 执行结果 */}
        {data.output != null && (
          <div className={styles.nodeOutput}>
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
      </Card>

      {/* 输出连接点 */}
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: 'var(--color-success)',
          width: 12,
          height: 12,
        }}
      />
    </>
  );
}

export default memo(NotificationNode);
