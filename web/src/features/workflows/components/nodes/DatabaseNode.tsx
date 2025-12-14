/**
 * Database Node - 数据库操作节点
 * 使用CSS Module + 设计Token系统
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
import styles from '../../styles/workflows.module.css';

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
          background: 'var(--color-primary-400)',
          width: 12,
          height: 12,
        }}
      />

      <Card
        className={`workflow-node ${getStatusColor(status, selected)} ${styles.nodeCardWide}`}
        styles={{ body: { padding: 0 } }}
      >
        {/* 节点头部 */}
        <div className={styles.nodeHeaderWrapper}>
          <div className={`${styles.nodeIcon} ${styles.nodeTypeDatabase}`}>
            {status === 'running' ? (
              <LoadingOutlined style={{ fontSize: 16 }} spin />
            ) : (
              <DatabaseOutlined style={{ fontSize: 16 }} role="img" />
            )}
          </div>
          <div className={styles.nodeTitleWrapper}>
            <h3 className={styles.nodeTitle}>
              数据库
            </h3>
          </div>
        </div>

        {/* 节点内容 */}
        <div className={styles.nodeContent}>
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
        </div>

        {/* 执行结果 */}
        {data.output && (
          <div className={styles.nodeOutput}>
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

export default memo(DatabaseNode);
