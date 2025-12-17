/**
 * CreateAgentPage - 创建 Agent 页面
 *
 * 功能：
 * 1. 显示页面标题和描述
 * 2. 渲染 CreateAgentForm 组件
 * 3. 创建成功后跳转到列表页
 * 4. 提供返回按钮
 *
 * 使用场景：
 * - 用户点击"创建 Agent"按钮后进入此页面
 * - 填写表单创建新的 Agent
 * - 创建成功后自动跳转到列表页
 */

import { App } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { CreateAgentForm } from '@/features/agents/components';
import { PageShell } from '@/shared/components/layout/PageShell';
import { NeoCard } from '@/shared/components/common/NeoCard';
import { NeoButton } from '@/shared/components/common/NeoButton';

import type { Agent } from '@/shared/types';
// import styles from '../styles/agents.module.css'; // Unused

export const CreateAgentPage: React.FC = () => {
  const navigate = useNavigate();
  const { message } = App.useApp();

  /**
   * 处理创建成功
   */
  const handleSuccess = (agent: Agent) => {
    message.success('Agent 创建成功，即将跳转到详情页');
    navigate(`/app/agents/${agent.id}`);
  };

  /**
   * 处理返回
   */
  const handleBack = () => {
    navigate('/app/agents');
  };

  return (
    <PageShell
      title="创建 Agent"
      description="填写以下信息来创建一个新的 Agent。Agent 会根据您提供的起点和目的，自动生成执行计划并完成任务。"
      actions={
        <NeoButton variant="ghost" icon={<ArrowLeftOutlined />} onClick={handleBack}>
          返回列表
        </NeoButton>

      }
    >
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        {/* 表单卡片 - 石质面板 */}
        <NeoCard variant="raised">
          <CreateAgentForm onSuccess={handleSuccess} />
        </NeoCard>
      </div>
    </PageShell>
  );
};

/**
 * 为什么使用 Card 包裹表单？
 * - 提供视觉边界，让表单更突出
 * - 符合 Ant Design 设计规范
 * - 提升页面美观度
 *
 * 为什么设置 maxWidth='800px'？
 * - 表单不应该太宽（影响可读性）
 * - 800px 是表单的最佳宽度
 * - 居中显示更美观
 *
 * 为什么使用 Space 组件？
 * - 自动管理子元素间距
 * - 避免手动设置 margin
 * - 保持间距一致性
 *
 * 为什么使用 Typography 组件？
 * - 提供统一的文字样式
 * - 符合 Ant Design 设计规范
 * - 自动响应主题变化
 */

export default CreateAgentPage;
