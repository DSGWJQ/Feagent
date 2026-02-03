/**
 * File Node - 文件操作节点
 * 使用CSS Module + 设计Token系统
 *
 * 功能：
 * - 文件读取（read）
 * - 文件写入（write）
 * - 文件追加（append）
 * - 文件删除（delete）
 * - 支持编码配置
 */

import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import { Card, Input } from 'antd';
import { FileOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

const { TextArea } = Input;

export interface FileNodeData extends Record<string, unknown> {
  operation: 'read' | 'write' | 'append' | 'delete';
  path: string;
  encoding: string;
  content?: string;
  status?: NodeStatus;
  output?: unknown;
}

type FileNodeType = Node<FileNodeData>;

function FileNode({ data, selected, id }: NodeProps<FileNodeType>) {
  const status = data.status || 'idle';
  const isWriteOperation = data.operation === 'write' || data.operation === 'append';

  return (
    <>
      {/* 输入连接点 */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: 'var(--color-neutral-600)',
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
          <div className={`${styles.nodeIcon} ${styles.nodeTypeFile}`}>
            {status === 'running' ? (
              <LoadingOutlined style={{ fontSize: 16 }} spin />
            ) : (
              <FileOutlined style={{ fontSize: 16 }} role="img" />
            )}
          </div>
          <div className={styles.nodeTitleWrapper}>
            <h3 className={styles.nodeTitle}>
              文件
            </h3>
          </div>
        </div>

        {/* 节点内容 */}
        <div className={styles.nodeContent}>
          {/* 操作类型 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              操作类型
            </label>
            <Input
              placeholder="read / write / append / delete"
              value={data.operation}
              readOnly
              style={{
                fontSize: 12,
                backgroundColor: '#f5f5f5',
              }}
            />
          </div>

          {/* 文件路径 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              文件路径
            </label>
            <Input
              placeholder="例如: /path/to/file.txt"
              value={data.path}
              readOnly
              style={{
                fontSize: 12,
                backgroundColor: '#f5f5f5',
              }}
            />
          </div>

          {/* 编码 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              编码
            </label>
            <Input
              placeholder="例如: utf-8, gbk"
              value={data.encoding}
              readOnly
              style={{
                fontSize: 12,
                backgroundColor: '#f5f5f5',
              }}
            />
          </div>

          {/* 内容（仅在 write/append 操作时显示） */}
          {isWriteOperation && data.content && (
            <div style={{ marginBottom: 12 }}>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  color: '#8c8c8c',
                  marginBottom: 4,
                }}
              >
                内容
              </label>
              <TextArea
                value={data.content}
                readOnly
                rows={4}
                style={{
                  fontSize: 12,
                  fontFamily: 'monospace',
                  backgroundColor: '#f5f5f5',
                }}
              />
            </div>
          )}
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

export default memo(FileNode);
