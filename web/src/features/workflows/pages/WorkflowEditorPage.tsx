/**
 * 工作流编辑器页面（带互斥锁）
 *
 * 功能：
 * - 拖拽编辑工作流节点和连线
 * - 保存工作流到后端
 * - 执行工作流（SSE 流式返回）
 * - 聊天/拖拽互斥锁
 *
 * 基于 V0 模板简化实现
 */

import { useCallback } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Alert, Button, Card, Space, Spin } from 'antd';
import { useWorkflow } from '@/hooks/useWorkflow';
import WorkflowInteractionProvider from '../contexts/WorkflowInteractionContext';
import WorkflowEditorPageWithMutex from './WorkflowEditorPageWithMutex';
import type { Workflow } from '../types/workflow';

/**
 * 工作流编辑器页面组件（带 Provider 包装）
 */
export const WorkflowEditorPage: React.FC = () => {
  const params = useParams<{ id: string }>();
  const workflowId = (params.id ?? '').trim();
  const navigate = useNavigate();

  const { isLoadingWorkflow, workflowError } = useWorkflow(workflowId);

  /**
   * 处理工作流更新
   */
  const handleWorkflowUpdate = useCallback((workflow: Workflow) => {
    console.log('Workflow updated:', workflow);
  }, []);

  // Defensive: editor must always be entered with an explicit workflow id.
  if (!workflowId) {
    return <Navigate to="/workflows/new" replace />;
  }

  // 显示加载状态
  if (isLoadingWorkflow) {
    return (
      <div style={{
        width: '100vw',
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0a0a0a',
        color: '#fafafa',
      }}>
        <Spin size="large" tip="加载工作流中...">
          <div style={{ width: 0, height: 0 }} />
        </Spin>
      </div>
    );
  }

  if (workflowError) {
    return (
      <div
        style={{
          width: '100vw',
          height: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#0a0a0a',
          color: '#fafafa',
          padding: 16,
        }}
      >
        <Card style={{ maxWidth: 640, width: '100%' }}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Alert
              type="error"
              showIcon
              message="工作流加载失败"
              description="当前 workflow 不存在或后端不可用。你可以返回首页重新创建。"
            />
            <Button type="primary" onClick={() => navigate('/', { replace: true })}>
              返回首页
            </Button>
          </Space>
        </Card>
      </div>
    );
  }

  return (
    <WorkflowInteractionProvider>
      <WorkflowEditorPageWithMutex
        workflowId={workflowId}
        onWorkflowUpdate={handleWorkflowUpdate}
      />
    </WorkflowInteractionProvider>
  );
};

export default WorkflowEditorPage;
