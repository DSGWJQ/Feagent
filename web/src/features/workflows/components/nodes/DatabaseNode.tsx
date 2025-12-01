/**
 * Database Node - 数据库操作节点
 *
 * 功能：
 * - 执行 SQL 查询（SELECT、INSERT、UPDATE、DELETE）
 * - 支持参数化查询
 * - 配置数据库连接
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, Input } from 'antd';
import { DatabaseOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';

const { TextArea } = Input;

export interface DatabaseNodeData {
  database_url: string;
  sql: string;
  params?: Record<string, any>;
  status?: NodeStatus;
  output?: any;
}

function DatabaseNode({ data, selected, id }: NodeProps<DatabaseNodeData>) {
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
              backgroundColor: '#1890ff',
              color: '#fff',
            }}
          >
            {status === 'running' ? (
              <LoadingOutlined style={{ fontSize: 16 }} spin />
            ) : (
              <DatabaseOutlined style={{ fontSize: 16 }} role="img" />
            )}
          </div>
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
              数据库
            </h3>
          </div>
        </div>

        {/* 节点内容 */}
        <div style={{ padding: '16px' }}>
          {/* 数据库连接 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              数据库连接
            </label>
            <Input
              placeholder="例如: sqlite:///agent_data.db"
              value={data.database_url}
              readOnly
              style={{
                fontSize: 12,
                backgroundColor: '#f5f5f5',
              }}
            />
          </div>

          {/* SQL 查询 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              SQL 查询
            </label>
            <TextArea
              placeholder="输入 SQL 查询，例如: SELECT * FROM users"
              value={data.sql}
              readOnly
              rows={3}
              style={{
                fontSize: 12,
                fontFamily: 'monospace',
                backgroundColor: '#f5f5f5',
              }}
            />
          </div>

          {/* 查询参数 */}
          {data.params && Object.keys(data.params).length > 0 && (
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  color: '#8c8c8c',
                  marginBottom: 4,
                }}
              >
                参数
              </label>
              <TextArea
                value={JSON.stringify(data.params, null, 2)}
                readOnly
                rows={2}
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
                查询结果
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
                {JSON.stringify(data.output, null, 2)}
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

export default memo(DatabaseNode);
