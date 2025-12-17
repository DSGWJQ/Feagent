/**
 * Agent 列表测试页面
 *
 * 为什么需要这个测试页面？
 * - 验证 API 客户端是否正常工作
 * - 验证 TanStack Query Hooks 是否正常工作
 * - 验证前后端连接是否正常
 *
 * 这是一个临时测试页面，后续会被 V0 生成的正式页面替换
 */

import { Spin, Alert, Space, Descriptions, Tag } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAgents, useCreateAgent, useDeleteAgent } from '@/shared/hooks';
import { PageShell } from '@/shared/components/layout/PageShell';
import { NeoCard } from '@/shared/components/common/NeoCard';
import { NeoButton } from '@/shared/components/common/NeoButton';
import type { CreateAgentDto } from '@/shared/types';
import styles from '../styles/agents.module.css';


export default function AgentListTest() {
  const navigate = useNavigate();

  // 使用 useAgents Hook 获取 Agent 列表
  const { data: agents, isLoading, error, refetch } = useAgents();

  // 使用 useCreateAgent Hook 创建 Agent
  const createAgent = useCreateAgent();

  // 使用 useDeleteAgent Hook 删除 Agent
  const deleteAgent = useDeleteAgent();

  /**
   * 处理创建测试 Agent
   */
  const handleCreateTest = () => {
    const testData: CreateAgentDto = {
      name: `测试 Agent ${new Date().toLocaleTimeString()}`,
      start: '有一个 CSV 文件需要分析',
      goal: '生成数据分析报告并发送邮件',
    };

    createAgent.mutate(testData);
  };

  /**
   * 处理删除 Agent
   */
  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation(); // 阻止冒泡，避免触发 Card 点击
    if (window.confirm('确认删除这个 Agent 吗？')) {
      deleteAgent.mutate(id);
    }
  };

  return (
    <PageShell
      title="Agent 管理"
      description="管理您的智能代理，查看状态与任务执行情况"
      actions={
        <Space>
          <NeoButton
            variant="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/agents/create')}
          >
            创建 Agent
          </NeoButton>
          <NeoButton
            variant="secondary"
            icon={<PlusOutlined />}
            onClick={handleCreateTest}
            loading={createAgent.isPending}
          >
            创建测试 Agent
          </NeoButton>
          <NeoButton
            variant="ghost"
            icon={<ReloadOutlined />}
            onClick={() => refetch()}
            loading={isLoading}
          >
            刷新
          </NeoButton>
        </Space>

      }
    >
      {/* 加载状态 */}
      {isLoading && (
        <div className={styles.loadingContainer}>
          <Spin size="large" />
          <p className={styles.loadingText}>加载中...</p>
        </div>
      )}

      {/* 错误状态 */}
      {error && (
        <Alert
          message="加载失败"
          description={
            <div>
              <p>无法连接到后端 API，请检查：</p>
              <ul>
                <li>后端服务是否启动（http://localhost:8000）</li>
                <li>CORS 是否配置正确</li>
                <li>网络连接是否正常</li>
              </ul>
              <p className={styles.textTertiary} style={{ marginTop: '8px' }}>
                错误信息：{error.message}
              </p>
            </div>
          }
          type="error"
          showIcon
        />
      )}

      {/* 成功状态 - 显示 Agent 列表 */}
      {!isLoading && !error && agents && (
        <div>
          {agents.length === 0 ? (
            <div className={styles.emptyContainer}>
              <p className={styles.emptyText}>暂无 Agent</p>
              <p>点击上方"创建测试 Agent"按钮创建一个测试数据</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--space-6)' }}>
              {agents.map((agent) => (
                <NeoCard
                  key={agent.id}
                  variant="raised"
                  onClick={() => navigate(`/app/agents/${agent.id}`)}
                  style={{ cursor: 'pointer' }}
                  title={
                    <Space>
                      <span style={{ fontWeight: 600, fontFamily: 'var(--font-family-serif)' }}>{agent.name}</span>
                      <Tag color="geekblue">ID: {agent.id.slice(0, 8)}</Tag>
                    </Space>
                  }
                >
                  <div style={{ marginBottom: 'var(--space-4)' }}>
                    <Descriptions column={1} size="small">
                      <Descriptions.Item label="起始状态">
                        {agent.start}
                      </Descriptions.Item>
                      <Descriptions.Item label="目标状态">
                        {agent.goal}
                      </Descriptions.Item>
                    </Descriptions>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--color-border-subtle)', paddingTop: 'var(--space-md)' }}>
                    <NeoButton
                      danger
                      variant="ghost"
                      size="small"
                      onClick={(e) => handleDelete(e, agent.id)}
                      loading={deleteAgent.isPending}
                    >
                      删除
                    </NeoButton>
                  </div>

                </NeoCard>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 底部说明 */}
      <Alert
        message="📝 说明"
        description={
          <div>
            <p><strong>这是一个临时测试页面，用于验证：</strong></p>
            <ul>
              <li>✅ API 客户端（agentsApi）是否正常工作</li>
              <li>✅ TanStack Query Hooks（useAgents, useCreateAgent, useDeleteAgent）是否正常工作</li>
              <li>✅ 前后端连接是否正常</li>
            </ul>
            <p style={{ marginTop: '8px' }}>
              <strong>下一步：</strong>使用 V0 生成正式的 Agent 管理页面
            </p>
          </div>
        }
        type="info"
        showIcon
        className={styles.marginTop}
        style={{ opacity: 0.8 }}
      />
    </PageShell>
  );
}

/**
 * 为什么创建这个测试页面？
 *
 * 1. 快速验证：
 *    - 不需要等 V0 生成页面，就可以验证基础设施是否正常
 *    - 发现问题可以立即修复
 *
 * 2. 调试工具：
 *    - 可以快速测试 API 调用
 *    - 可以查看数据结构
 *    - 可以测试错误处理
 *
 * 3. 参考示例：
 *    - 展示如何使用 Hooks
 *    - 展示如何处理加载/错误状态
 *    - 为 V0 生成的页面提供参考
 *
 * 后续：
 * - 当 V0 生成正式页面后，可以删除这个测试页面
 * - 或者保留作为开发调试工具
 */
