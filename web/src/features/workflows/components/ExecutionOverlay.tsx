/**
 * 执行进度覆盖层组件
 *
 * 在节点旁渲染状态图标、输出摘要和运行顺序号
 */

import React, { useMemo } from 'react';
import { Badge, Tooltip, Space, Typography } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { useReactFlow } from '@xyflow/react';
import type { Node } from '@xyflow/react';
import { NodeStatusMap, NodeOutputMap } from '../hooks/useWorkflowExecution';

const { Text } = Typography;

interface ExecutionOverlayProps {
  nodeStatusMap: NodeStatusMap;
  nodeOutputMap: NodeOutputMap;
  currentNodeId: string | null;
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
  node: Node;
  status?: string;
  output?: any;
  order?: number;
  isCurrent: boolean;
}> = ({ node, status, output, order, isCurrent }) => {
  const statusConfig = useMemo(() => {
    switch (status) {
      case 'running':
        return {
          icon: <LoadingOutlined spin style={{ color: '#1890ff' }} />,
          color: '#1890ff',
          text: '运行中',
        };
      case 'completed':
        return {
          icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
          color: '#52c41a',
          text: '已完成',
        };
      case 'error':
        return {
          icon: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
          color: '#ff4d4f',
          text: '错误',
        };
      default:
        return {
          icon: <ClockCircleOutlined style={{ color: '#8c8c8c' }} />,
          color: '#8c8c8c',
          text: '待执行',
        };
    }
  }, [status]);

  const outputSummary = useMemo(() => {
    if (!output) return null;

    if (typeof output === 'string') {
      return output.length > 50 ? output.substring(0, 50) + '...' : output;
    }

    if (typeof output === 'object' && output.content) {
      return output.content.length > 50 ? output.content.substring(0, 50) + '...' : output.content;
    }

    return JSON.stringify(output).substring(0, 50) + '...';
  }, [output]);

  return (
    <div
      style={{
        position: 'absolute',
        top: -35,
        left: 0,
        right: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '2px 8px',
        background: 'rgba(0, 0, 0, 0.8)',
        borderRadius: '4px 4px 0 0',
        zIndex: 1000,
      }}
    >
      <Space size={4}>
        {order !== undefined && (
          <Badge
            count={order + 1}
            size="small"
            style={{
              backgroundColor: isCurrent ? '#1890ff' : '#8c8c8c',
            }}
          />
        )}
        <span style={{ color: '#fff', fontSize: '12px' }}>
          {node.data?.name || node.id}
        </span>
      </Space>

      <Space size={4}>
        {statusConfig.icon}
        <span style={{ color: statusConfig.color, fontSize: '12px' }}>
          {statusConfig.text}
        </span>
      </Space>

      {outputSummary && (
        <Tooltip title={typeof output === 'object' ? JSON.stringify(output, null, 2) : output}>
          <Text
            style={{
              color: '#8c8c8c',
              fontSize: '11px',
              maxWidth: 150,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {outputSummary}
          </Text>
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
  currentNodeId,
  isExecuting,
  nodes,
}) => {
  const { getIntersectingNodes } = useReactFlow();

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
          node={node}
          status={nodeStatusMap[node.id]}
          output={nodeOutputMap[node.id]}
          order={executionOrder[node.id]}
          isCurrent={node.id === currentNodeId}
        />
      ))}
    </>
  );
};

export default ExecutionOverlay;
