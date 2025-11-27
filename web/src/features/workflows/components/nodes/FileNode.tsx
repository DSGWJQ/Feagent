/**
 * File Node - 文件操作节点
 *
 * 功能：
 * - 文件读取（read）
 * - 文件写入（write）
 * - 文件追加（append）
 * - 文件删除（delete）
 * - 支持编码配置
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, Input } from 'antd';
import { FileOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

const { TextArea } = Input;

export interface FileNodeData {
  operation: 'read' | 'write' | 'append' | 'delete';
  path: string;
  encoding: string;
  content?: string;
  status?: NodeStatus;
  output?: any;
}

function FileNode({ data, selected, id }: NodeProps<FileNodeData>) {
  const status = data.status || 'idle';
  const isWriteOperation = data.operation === 'write' || data.operation === 'append';

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
        bodyStyle={{ padding: 0 }}
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
              backgroundColor: '#722ed1',
              color: '#fff',
            }}
          >
            {status === 'running' ? (
              <LoadingOutlined style={{ fontSize: 16 }} spin />
            ) : (
              <FileOutlined style={{ fontSize: 16 }} role="img" />
            )}
          </div>
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
              文件
            </h3>
          </div>
        </div>

        {/* 节点内容 */}
        <div style={{ padding: '16px' }}>
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

export default memo(FileNode);
