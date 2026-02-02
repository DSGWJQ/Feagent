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

import { useState, useCallback, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Alert, App, Button, Card, Input, Spin, Space, Typography } from 'antd';
import { useWorkflow } from '@/hooks/useWorkflow';
import { chatCreateWorkflowStreaming, type PlanningSseEvent } from '../api/workflowsApi';
import WorkflowInteractionProvider from '../contexts/WorkflowInteractionContext';
import WorkflowEditorPageWithMutex from './WorkflowEditorPageWithMutex';
import type { Workflow } from '../types/workflow';

function generateRunId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `run_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function getDefaultChatCreateProjectId(): string {
  const raw = (import.meta.env.VITE_DEFAULT_PROJECT_ID ?? '').toString().trim();
  // Keep <=36 chars to match backend DB constraints (projects.id is String(36)).
  return raw.length > 0 ? raw.slice(0, 36) : 'default';
}

function extractWorkflowId(event: PlanningSseEvent): string | null {
  const metadata = event.metadata ?? {};
  const candidate =
    metadata['workflow_id'] ??
    metadata['workflowId'] ??
    (typeof metadata['workflow'] === 'object' && metadata['workflow'] !== null
      ? (metadata['workflow'] as Record<string, unknown>)?.id
      : null);
  if (typeof candidate !== 'string') {
    return null;
  }
  const trimmed = candidate.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/**
 * 工作流编辑器页面组件（带 Provider 包装）
 */
export const WorkflowEditorPage: React.FC = () => {
  const params = useParams<{ id: string }>();
  const workflowId = params.id || '';
  const navigate = useNavigate();
  const { message } = App.useApp();

  const { isLoadingWorkflow, workflowError } = useWorkflow(workflowId);
  const [isCreating, setIsCreating] = useState(false);
  const [createPrompt, setCreatePrompt] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [createProgress, setCreateProgress] = useState<string | null>(null);

  const cancelCreateRef = useRef<(() => void) | null>(null);
  const hasNavigatedRef = useRef(false);
  const createTimeoutRef = useRef<number | null>(null);

  /**
   * 处理工作流更新
   */
  const handleWorkflowUpdate = useCallback((workflow: Workflow) => {
    console.log('Workflow updated:', workflow);
  }, []);

  /**
   * 创建新工作流（chat-create/stream）
   */
  const createNewWorkflow = useCallback(async () => {
    const trimmed = createPrompt.trim();
    if (!trimmed || isCreating) return;

    const projectId = getDefaultChatCreateProjectId();

    setIsCreating(true);
    setCreateError(null);
    setCreateProgress(null);
    hasNavigatedRef.current = false;

    if (createTimeoutRef.current) {
      window.clearTimeout(createTimeoutRef.current);
    }

    try {
      let eventsSeen = 0;

      const finishWithError = (errorMessage: string) => {
        if (hasNavigatedRef.current) return;
        cancelCreateRef.current?.();
        cancelCreateRef.current = null;
        if (createTimeoutRef.current) {
          window.clearTimeout(createTimeoutRef.current);
          createTimeoutRef.current = null;
        }
        setIsCreating(false);
        setCreateError(errorMessage);
      };

      // Contract: workflow_id should arrive very early in the SSE stream.
      // In practice (especially on Windows + SQLite cold writes), persisting the initial workflow can
      // take >10s, so keep this timeout moderately relaxed to avoid false negatives.
      createTimeoutRef.current = window.setTimeout(() => {
        finishWithError('创建超时：未在预期时间内获取 workflow_id');
      }, 20_000);

      cancelCreateRef.current = chatCreateWorkflowStreaming(
        { message: trimmed, run_id: generateRunId(), project_id: projectId },
        (event) => {
          eventsSeen += 1;

          if (event.type === 'thinking' && event.content) {
            setCreateProgress(event.content);
          }

          if (event.type === 'error') {
            finishWithError(event.content || '创建失败：后端返回 error 事件');
            return;
          }

          const newWorkflowId = extractWorkflowId(event);
          if (newWorkflowId) {
            hasNavigatedRef.current = true;
            cancelCreateRef.current?.();
            cancelCreateRef.current = null;
            if (createTimeoutRef.current) {
              window.clearTimeout(createTimeoutRef.current);
              createTimeoutRef.current = null;
            }
            setIsCreating(false);
            message.success('工作流已创建，正在进入编辑器...');
            navigate(`/workflows/${newWorkflowId}/edit?projectId=${encodeURIComponent(projectId)}`, {
              replace: true,
            });
            return;
          }

          if (eventsSeen >= 2) {
            finishWithError('协议异常：未在前 2 个事件内获取 workflow_id');
          }
        },
        (error) => {
          finishWithError(error?.message || '创建失败：网络错误');
        }
      );
    } catch (error: unknown) {
      console.error('Failed to create workflow:', error);
      setIsCreating(false);
      setCreateError('创建失败：未知错误');
    } finally {
      // 注意：在成功拿到 workflow_id 后会 navigate，组件可能被卸载；这里不强制 setIsCreating(false)
    }
  }, [createPrompt, isCreating, navigate, message]);

  useEffect(() => {
    return () => {
      cancelCreateRef.current?.();
      cancelCreateRef.current = null;
      if (createTimeoutRef.current) {
        window.clearTimeout(createTimeoutRef.current);
        createTimeoutRef.current = null;
      }
    };
  }, []);

  if (!workflowId) {
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
        <Card style={{ maxWidth: 720, width: '100%' }}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div>
              <Typography.Title level={3} style={{ margin: 0 }}>
                创建对话工作流
              </Typography.Title>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                输入一句话，系统将创建 workflow 并自动跳转到编辑器。
              </Typography.Paragraph>
            </div>

            {createError ? <Alert type="error" showIcon message={createError} /> : null}
            {createProgress ? (
              <Alert type="info" showIcon message="AI 正在处理" description={createProgress} />
            ) : null}

            <Input.TextArea
              data-testid="workflow-chat-create-textarea"
              value={createPrompt}
              onChange={(e) => setCreatePrompt(e.target.value)}
              placeholder="例如：帮我生成一个“用户注册与欢迎邮件”工作流"
              autoSize={{ minRows: 4, maxRows: 10 }}
              disabled={isCreating}
            />

            <Space>
              <Button
                type="primary"
                onClick={() => void createNewWorkflow()}
                disabled={!createPrompt.trim() || isCreating}
                data-testid="workflow-chat-create-submit"
              >
                创建并进入编辑器
              </Button>
              {isCreating ? <Spin size="small" /> : null}
            </Space>
          </Space>
        </Card>
      </div>
    );
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
