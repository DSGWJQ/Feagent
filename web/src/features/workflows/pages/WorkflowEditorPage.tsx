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

import { useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { message, Spin } from 'antd';
import { useWorkflow } from '@/hooks/useWorkflow';
import { createWorkflow } from '../api/workflowsApi';
import WorkflowInteractionProvider from '../contexts/WorkflowInteractionContext';
import WorkflowEditorPageWithMutex from './WorkflowEditorPageWithMutex';

/**
 * 工作流编辑器页面组件（带 Provider 包装）
 */
export const WorkflowEditorPage: React.FC = () => {
  const params = useParams<{ id: string }>();
  const workflowId = params.id || '';
  const navigate = useNavigate();

  const { workflowData, isLoadingWorkflow, workflowError } = useWorkflow(workflowId);
  const [isCreating, setIsCreating] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  /**
   * 处理工作流更新
   */
  const handleWorkflowUpdate = useCallback((workflow: any) => {
    console.log('Workflow updated:', workflow);
  }, []);

  /**
   * 创建新工作流
   */
  const createNewWorkflow = useCallback(async () => {
    if (isCreating) return;

    setIsCreating(true);
    try {
      const newWorkflow = await createWorkflow({
        name: '新建工作流',
        description: 'AI 自动生成的工作流',
        nodes: [],
        edges: [],
      });

      navigate(`/workflows/${newWorkflow.id}/edit`, { replace: true });
      message.success('工作流已创建');
    } catch (error: any) {
      console.error('Failed to create workflow:', error);
      message.error(`创建工作流失败: ${error.message}`);
    } finally {
      setIsCreating(false);
    }
  }, [isCreating, navigate]);

  /**
   * 初始化工作流
   */
  useEffect(() => {
    // 如果没有 workflowId，创建新的
    if (!workflowId && !isCreating) {
      createNewWorkflow();
      return;
    }

    // 如果有错误或数据不存在，创建新的
    if (workflowError && !isCreating && !isInitialized) {
      createNewWorkflow();
      return;
    }

    // 标记为已初始化
    if (workflowData && !isInitialized) {
      setIsInitialized(true);
    }
  }, [workflowId, workflowData, workflowError, isCreating, isInitialized, createNewWorkflow]);

  // 显示加载状态
  if (isLoadingWorkflow || isCreating) {
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
        <Spin size="large" tip={isCreating ? "创建工作流中..." : "加载工作流中..."} />
      </div>
    );
  }

  // 如果还没有 workflowId，显示加载
  if (!workflowId) {
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
        <Spin size="large" tip="准备工作流编辑器..." />
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
