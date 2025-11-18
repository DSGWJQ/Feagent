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

import { Button, Card, Spin, Alert, Space, Descriptions, Tag } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAgents, useCreateAgent, useDeleteAgent } from '@/shared/hooks';
import type { CreateAgentDto } from '@/shared/types';

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
  const handleDelete = (id: string) => {
    if (window.confirm('确认删除这个 Agent 吗？')) {
      deleteAgent.mutate(id);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Card
        title="🧪 Agent 列表"
        extra={
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate('/agents/create')}
            >
              创建 Agent
            </Button>
            <Button
              type="default"
              icon={<PlusOutlined />}
              onClick={handleCreateTest}
              loading={createAgent.isPending}
            >
              创建测试 Agent
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => refetch()}
              loading={isLoading}
            >
              刷新
            </Button>
          </Space>
        }
      >
        {/* 加载状态 */}
        {isLoading && (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <p style={{ marginTop: '16px', color: '#666' }}>加载中...</p>
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
                <p style={{ marginTop: '8px', color: '#999' }}>
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
            <Alert
              message="✅ API 连接成功！"
              description={`成功获取到 ${agents.length} 个 Agent`}
              type="success"
              showIcon
              style={{ marginBottom: '16px' }}
            />

            {agents.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                <p>暂无 Agent</p>
                <p>点击上方"创建测试 Agent"按钮创建一个测试数据</p>
              </div>
            ) : (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                {agents.map((agent) => (
                  <Card
                    key={agent.id}
                    size="small"
                    title={
                      <Space>
                        <span>{agent.name}</span>
                        <Tag color="blue">ID: {agent.id.slice(0, 8)}</Tag>
                      </Space>
                    }
                    extra={
                      <Button
                        danger
                        size="small"
                        onClick={() => handleDelete(agent.id)}
                        loading={deleteAgent.isPending}
                      >
                        删除
                      </Button>
                    }
                  >
                    <Descriptions column={1} size="small">
                      <Descriptions.Item label="起始状态">
                        {agent.start}
                      </Descriptions.Item>
                      <Descriptions.Item label="目标状态">
                        {agent.goal}
                      </Descriptions.Item>
                      <Descriptions.Item label="创建时间">
                        {new Date(agent.created_at).toLocaleString('zh-CN')}
                      </Descriptions.Item>
                      <Descriptions.Item label="更新时间">
                        {new Date(agent.updated_at).toLocaleString('zh-CN')}
                      </Descriptions.Item>
                    </Descriptions>
                  </Card>
                ))}
              </Space>
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
          style={{ marginTop: '16px' }}
        />
      </Card>
    </div>
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
