/**
 * AgentDetailPage - Agent 详情页
 *
 * 功能：
 * 1. 显示 Agent 基本信息（名称、起点、目的、创建时间）
 * 2. 显示 Agent 的 Tasks 列表
 * 3. 加载状态（Spin）
 * 4. 错误处理（Agent 不存在时显示错误）
 * 5. 返回按钮
 *
 * 使用场景：
 * - 用户创建 Agent 后自动跳转到此页面
 * - 用户点击 Agent 列表中的某个 Agent 进入此页面
 */

import { Button, Spin, Alert, Descriptions, List, Tag, Space } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useAgent } from '@/shared/hooks';
import { PageShell } from '@/shared/components/layout/PageShell';
import { NeoCard } from '@/shared/components/common/NeoCard';
import type { AgentTask } from '@/shared/types';
import styles from '../styles/agents.module.css';

export const AgentDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();

  // 使用 useAgent Hook 获取 Agent 详情
  const { data: agent, isLoading, error } = useAgent(id!);

  /**
   * 处理返回
   */
  const handleBack = () => {
    navigate('/app/agents');
  };

  /**
   * 渲染加载状态
   */
  if (isLoading) {
    return (
      <div className={styles.loadingContainer}>
        <Spin size="large" />
        <p className={styles.loadingText}>加载中...</p>
      </div>
    );
  }

  /**
   * 渲染错误状态
   */
  if (error || !agent) {
    return (
      <div className={styles.pageContainer}>
        <Alert
          message="加载失败"
          description={error?.message || 'Agent 不存在'}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={handleBack}>
              返回列表
            </Button>
          }
        />
      </div>
    );
  }

  /**
   * 渲染 Task 状态标签
   */
  const renderTaskStatus = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: '等待执行' },
      running: { color: 'processing', text: '执行中' },
      succeeded: { color: 'success', text: '执行成功' },
      failed: { color: 'error', text: '执行失败' },
    };

    const config = statusMap[status] || { color: 'default', text: status };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  /**
   * 渲染 Tasks 列表
   */
  const renderTasks = () => {
    const tasks = agent.tasks || [];

    if (tasks.length === 0) {
      return (
        <NeoCard title="执行任务" className={styles.marginTop}>
          <div className={styles.emptyContainer}>
            <p>暂无任务</p>
          </div>
        </NeoCard>
      );
    }

    return (
      <NeoCard title="执行任务" className={styles.marginTop}>
        <List
          dataSource={tasks}
          renderItem={(task: AgentTask, index: number) => (
            <List.Item>
              <List.Item.Meta
                title={
                  <Space>
                    <span>{index + 1}. {task.name}</span>
                    {renderTaskStatus(task.status)}
                  </Space>
                }
                description={task.description || '暂无描述'}
              />
            </List.Item>
          )}
        />
      </NeoCard>
    );
  };

  return (
    <PageShell
      title={agent.name}
      description={`ID: ${agent.id}`}
      actions={
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={handleBack}
        >
          返回列表
        </Button>
      }
    >
      <Space direction="vertical" size="large" className={styles.spaceFullWidth}>
        {/* Agent 基本信息 - 石碑铭文风 */}
        <NeoCard title="基础信息">
          <Descriptions column={1}>
            <Descriptions.Item label="起点">
              {agent.start}
            </Descriptions.Item>
            <Descriptions.Item label="目的">
              {agent.goal}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {new Date(agent.created_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
          </Descriptions>
        </NeoCard>

        {/* Tasks 列表 */}
        {renderTasks()}
      </Space>
    </PageShell>
  );
};

/**
 * 为什么使用 Descriptions 组件？
 * - 适合展示键值对数据
 * - 自动处理布局和对齐
 * - 符合 Ant Design 设计规范
 *
 * 为什么使用 List 组件？
 * - 适合展示列表数据
 * - 自动处理间距和分隔线
 * - 支持 Meta 信息（标题、描述）
 *
 * 为什么使用 Space 组件？
 * - 自动管理子元素间距
 * - 避免手动设置 margin
 * - 保持间距一致性
 *
 * 为什么分离 renderTasks 函数？
 * - 提高代码可读性
 * - 方便测试
 * - 便于后续优化（如添加分页、搜索等）
 */

export default AgentDetailPage;
