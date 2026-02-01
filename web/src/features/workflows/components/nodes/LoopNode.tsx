/**
 * Loop Node - 循环节点
 * 使用CSS Module + 设计Token系统
 *
 * 功能：
 * - for_each 循环（遍历数组）
 * - range 循环（指定范围）
 * - while 循环（条件循环）
 * - 执行循环体代码
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, Input, Progress } from 'antd';
import { RetweetOutlined, LoadingOutlined } from '@ant-design/icons';
import { getStatusColor, type NodeStatus } from '../../utils/nodeUtils';
import styles from '../../styles/workflows.module.css';

const { TextArea } = Input;

export interface LoopNodeData {
  // Back-compat: keep `for` + `iterations` for older saved workflows.
  type: 'for_each' | 'range' | 'while' | 'for';
  array?: string;
  code?: string;
  start?: number;
  end?: number;
  step?: number;
  iterations?: number;
  condition?: string;
  max_iterations?: number;
  current_index?: number;
  total?: number;
  status?: NodeStatus;
  output?: unknown;
}

function LoopNode({ data, selected, id }: NodeProps<LoopNodeData>) {
  const status = data.status || 'idle';
  const hasProgress = data.current_index !== undefined && data.total !== undefined;
  const progressPercent = hasProgress ? Math.round((data.current_index! / data.total!) * 100) : 0;

  return (
    <>
      {/* 输入连接点 */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: 'var(--color-accent-agent)',
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
          <div className={`${styles.nodeIcon} ${styles.nodeTypeLoop}`}>
            {status === 'running' ? (
              <LoadingOutlined style={{ fontSize: 16 }} spin />
            ) : (
              <RetweetOutlined style={{ fontSize: 16 }} role="img" />
            )}
          </div>
          <div className={styles.nodeTitleWrapper}>
            <h3 className={styles.nodeTitle}>
              循环
            </h3>
          </div>
        </div>

        {/* 节点内容 */}
        <div className={styles.nodeContent}>
          {/* 循环类型 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              循环类型
            </label>
            <Input
              placeholder="for_each / range / while"
              value={data.type}
              readOnly
              style={{
                fontSize: 12,
                backgroundColor: '#f5f5f5',
              }}
            />
          </div>

          {data.type === 'for_each' && (
            <div style={{ marginBottom: 12 }}>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  color: '#8c8c8c',
                  marginBottom: 4,
                }}
              >
                数组变量
              </label>
              <Input
                placeholder="例如: items, userList"
                value={data.array ?? ''}
                readOnly
                style={{
                  fontSize: 12,
                  backgroundColor: '#f5f5f5',
                }}
              />
            </div>
          )}

          {(data.type === 'range' || data.type === 'for') && (
            <div style={{ marginBottom: 12 }}>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  color: '#8c8c8c',
                  marginBottom: 4,
                }}
              >
                范围
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                <Input
                  placeholder="start"
                  value={data.start ?? 0}
                  readOnly
                  style={{
                    fontSize: 12,
                    backgroundColor: '#f5f5f5',
                  }}
                />
                <Input
                  placeholder="end"
                  value={data.end ?? data.iterations ?? ''}
                  readOnly
                  style={{
                    fontSize: 12,
                    backgroundColor: '#f5f5f5',
                  }}
                />
                <Input
                  placeholder="step"
                  value={data.step ?? 1}
                  readOnly
                  style={{
                    fontSize: 12,
                    backgroundColor: '#f5f5f5',
                  }}
                />
              </div>
            </div>
          )}

          {data.type === 'while' && (
            <div style={{ marginBottom: 12 }}>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  color: '#8c8c8c',
                  marginBottom: 4,
                }}
              >
                条件
              </label>
              <Input
                placeholder="iteration < 10"
                value={data.condition ?? ''}
                readOnly
                style={{
                  fontSize: 12,
                  backgroundColor: '#f5f5f5',
                }}
              />
              <div style={{ marginTop: 8 }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: 12,
                    color: '#8c8c8c',
                    marginBottom: 4,
                  }}
                >
                  最大迭代次数
                </label>
                <Input
                  placeholder="max_iterations"
                  value={data.max_iterations ?? ''}
                  readOnly
                  style={{
                    fontSize: 12,
                    backgroundColor: '#f5f5f5',
                  }}
                />
              </div>
            </div>
          )}

          {/* 循环体代码 */}
          <div style={{ marginBottom: 12 }}>
            <label
              style={{
                display: 'block',
                fontSize: 12,
                color: '#8c8c8c',
                marginBottom: 4,
              }}
            >
              循环体代码
            </label>
            <TextArea
              placeholder="例如: result = processItem(item)"
              value={data.code ?? ''}
              readOnly
              rows={4}
              style={{
                fontSize: 12,
                fontFamily: 'monospace',
                backgroundColor: '#f5f5f5',
              }}
            />
          </div>

          {/* 执行进度（运行时） */}
          {hasProgress && (
            <div style={{ marginBottom: 12 }}>
              <label
                style={{
                  display: 'block',
                  fontSize: 12,
                  color: '#8c8c8c',
                  marginBottom: 4,
                }}
              >
                执行进度
              </label>
              <div
                style={{
                  fontSize: 12,
                  marginBottom: 4,
                  color: '#1890ff',
                }}
              >
                {data.current_index} / {data.total}
              </div>
              <Progress
                percent={progressPercent}
                size="small"
                strokeColor="#1890ff"
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

export default memo(LoopNode);
