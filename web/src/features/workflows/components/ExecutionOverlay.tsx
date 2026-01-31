/**
 * 执行进度覆盖层组件
 *
 * 在节点旁渲染状态图标、输出摘要和运行顺序号
 * 使用CSS Module + 设计Token系统
 */

import React, { useMemo } from 'react';
import { Tooltip } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import type { Node } from '@xyflow/react';
import type { NodeStatusMap, NodeOutputMap } from '../hooks/useWorkflowExecution';
import styles from '../styles/workflows.module.css';

interface ExecutionOverlayProps {
  nodeStatusMap: NodeStatusMap;
  nodeOutputMap: NodeOutputMap;
  isExecuting: boolean;
  nodes: Node[];
}

interface NodeExecutionOrder {
  [nodeId: string]: number;
}

/**
 * 节点执行状态组件
 */
const NodeExecutionStatus: React.FC<{
  status?: string;
  output?: unknown;
  order?: number;
}> = ({ status, output, order }) => {
  const statusConfig = useMemo(() => {
    switch (status) {
      case 'running':
        return {
          icon: <LoadingOutlined spin className={styles.statusRunning} />,
          text: '运行中',
        };
      case 'completed':
        return {
          icon: <CheckCircleOutlined className={styles.statusCompleted} />,
          text: '已完成',
        };
      case 'error':
        return {
          icon: <CloseCircleOutlined className={styles.statusError} />,
          text: '错误',
        };
      default:
        return {
          icon: <ClockCircleOutlined className={styles.statusPending} />,
          text: '待执行',
        };
    }
  }, [status]);

  const outputSummary = useMemo(() => {
    if (!output) return null;

    if (typeof output === 'string') {
      return output.length > 50 ? output.substring(0, 50) + '...' : output;
    }

    if (output && typeof output === 'object' && 'content' in output) {
      const content = (output as { content?: unknown }).content;
      if (typeof content === 'string') {
        return content.length > 50 ? content.substring(0, 50) + '...' : content;
      }
    }

    return JSON.stringify(output).substring(0, 50) + '...';
  }, [output]);

  return (
    <div className={styles.executionOverlay}>
      <Tooltip title={`状态: ${statusConfig.text}`}>
        <div className={styles.executionStatus}>
          {order !== undefined && (
            <span className={styles.executionOrder}>
              #{order + 1}
            </span>
          )}
          <span>{statusConfig.icon}</span>
        </div>
      </Tooltip>

      {output && outputSummary && (
        <Tooltip title={typeof output === 'string' ? output : JSON.stringify(output, null, 2)}>
          <div className={styles.executionOutput}>
            {outputSummary}
          </div>
        </Tooltip>
      )}
    </div>
  );
};

/**
 * 执行进度覆盖层组件
 */
export const ExecutionOverlay: React.FC<ExecutionOverlayProps> = ({
  nodeStatusMap,
  nodeOutputMap,
  isExecuting,
  nodes,
}) => {
  // 计算节点执行顺序
  const executionOrder = useMemo<NodeExecutionOrder>(() => {
    const order: NodeExecutionOrder = {};
    let counter = 0;

    // 根据节点状态和位置确定执行顺序
    nodes.forEach((node) => {
      if (nodeStatusMap[node.id]) {
        order[node.id] = counter++;
      }
    });

    return order;
  }, [nodes, nodeStatusMap]);

  // 获取需要显示状态的节点
  const visibleNodes = useMemo(() => {
    if (!isExecuting && Object.keys(nodeStatusMap).length === 0) {
      return [];
    }

    return nodes.filter((node) => {
      // 显示有状态的节点
      if (nodeStatusMap[node.id]) {
        return true;
      }

      // 如果正在执行，显示所有节点
      if (isExecuting) {
        return true;
      }

      return false;
    });
  }, [nodes, nodeStatusMap, isExecuting]);

  if (visibleNodes.length === 0) {
    return null;
  }

  return (
    <>
      {visibleNodes.map((node) => (
        <NodeExecutionStatus
          key={node.id}
          status={nodeStatusMap[node.id]}
          output={nodeOutputMap[node.id]}
          order={executionOrder[node.id]}
        />
      ))}
    </>
  );
};

export default ExecutionOverlay;
