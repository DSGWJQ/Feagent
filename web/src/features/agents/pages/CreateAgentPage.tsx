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

import { Card, Button, Space, Typography } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { CreateAgentForm } from '@/features/agents/components';
import type { Agent } from '@/shared/types';

const { Title, Paragraph } = Typography;

export const CreateAgentPage: React.FC = () => {
  const navigate = useNavigate();

  /**
   * 处理创建成功
   *
   * 流程：
   * 1. 表单提交成功
   * 2. 跳转到详情页
   *
   * 为什么跳转到详情页？
   * - 让用户立即看到生成的任务列表
   * - 符合用户预期（创建完成后查看详情）
   * - 提供更好的用户体验
   */
  const handleSuccess = (agent: Agent) => {
    navigate(`/agents/${agent.id}`);
  };

  /**
   * 处理返回
   *
   * 为什么需要返回按钮？
   * - 用户可能改变主意，不想创建了
   * - 提供明确的退出路径
   * - 提升用户体验
   */
  const handleBack = () => {
    navigate('/agents');
  };

  return (
    <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto' }}>
      {/* 页面头部 */}
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 返回按钮 */}
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
          type="text"
        >
          返回列表
        </Button>

        {/* 页面标题和描述 */}
        <div>
          <Title level={2}>创建 Agent</Title>
          <Paragraph type="secondary">
            填写以下信息来创建一个新的 Agent。Agent 会根据您提供的起点和目的，自动生成执行计划并完成任务。
          </Paragraph>
        </div>

        {/* 表单卡片 */}
        <Card>
          <CreateAgentForm onSuccess={handleSuccess} />
        </Card>
      </Space>
    </div>
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
