/**
 * NotificationNode 组件测试
 *
 * 测试策略（TDD）：
 * 1. 渲染测试：节点能正常渲染，显示标题和图标
 * 2. 通知类型测试：类型选择（webhook/email/slack）
 * 3. 主题配置测试：主题输入框正常工作
 * 4. 消息内容测试：消息文本框能正常显示
 * 5. URL 配置测试：webhook URL 输入
 * 6. 选项测试：include_input 等选项
 * 7. 连接点测试：输入和输出连接点存在
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import NotificationNode from '../NotificationNode';

// 包装组件（提供 ReactFlow 上下文）
const renderWithReactFlow = (ui: React.ReactElement) => {
  return render(<ReactFlowProvider>{ui}</ReactFlowProvider>);
};

describe('NotificationNode - TDD', () => {
  describe('渲染测试', () => {
    it('应该渲染通知节点并显示标题', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test Notification',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该显示"通知"标题
      expect(screen.getByText('通知')).toBeInTheDocument();
    });

    it('应该显示通知图标', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test Notification',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该有通知图标（通过 role 查找）
      const icon = screen.getByRole('img', { hidden: true });
      expect(icon).toBeInTheDocument();
    });
  });

  describe('通知类型测试', () => {
    it('应该显示通知类型标签', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该有"通知类型"标签
      expect(screen.getByText('通知类型')).toBeInTheDocument();
    });

    it('应该显示当前的通知类型', () => {
      const mockData = {
        type: 'email',
        subject: 'Email Test',
        message: 'Email message',
        url: '',
        include_input: false,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该显示 email 类型
      expect(screen.getByDisplayValue('email')).toBeInTheDocument();
    });

    it('通知类型应该是只读的', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      const typeInput = screen.getByDisplayValue('webhook');
      expect(typeInput).toHaveAttribute('readonly');
    });
  });

  describe('主题配置测试', () => {
    it('应该显示主题标签', () => {
      const mockData = {
        type: 'webhook',
        subject: '',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该有"主题"标签
      expect(screen.getByText('主题')).toBeInTheDocument();
    });

    it('应该显示现有的主题', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Important Alert: System Down',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该显示主题
      const subjectInput = screen.getByDisplayValue('Important Alert: System Down');
      expect(subjectInput).toBeInTheDocument();
    });

    it('主题应该是只读的', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test Subject',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      const subjectInput = screen.getByDisplayValue('Test Subject');
      expect(subjectInput).toHaveAttribute('readonly');
    });
  });

  describe('消息内容测试', () => {
    it('应该显示消息标签', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: '',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该有"消息"标签
      expect(screen.getByText('消息')).toBeInTheDocument();
    });

    it('应该显示消息内容', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'This is a test notification message.\nWith multiple lines.',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该显示消息内容
      const messageTextarea = screen.getByDisplayValue(/This is a test notification message/);
      expect(messageTextarea).toBeInTheDocument();
    });

    it('消息应该是只读的', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      const messageTextarea = screen.getByDisplayValue('Test message');
      expect(messageTextarea).toHaveAttribute('readonly');
    });
  });

  describe('URL 配置测试', () => {
    it('应该显示 URL 标签（webhook 类型）', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com/notify',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该有"Webhook URL"标签
      expect(screen.getByText('Webhook URL')).toBeInTheDocument();
    });

    it('应该显示现有的 webhook URL', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该显示 URL
      const urlInput = screen.getByDisplayValue(/hooks.slack.com/);
      expect(urlInput).toBeInTheDocument();
    });

    it('webhook URL 应该是只读的', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      const urlInput = screen.getByDisplayValue('https://webhook.example.com');
      expect(urlInput).toHaveAttribute('readonly');
    });
  });

  describe('选项配置测试', () => {
    it('应该显示 include_input 选项标签', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该有"包含输入数据"相关文本
      expect(screen.getByText(/包含输入数据/)).toBeInTheDocument();
    });

    it('应该显示 include_input 的当前值', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该显示 true
      expect(screen.getByText(/是|true/i)).toBeInTheDocument();
    });
  });

  describe('连接点测试', () => {
    it('应该有输入连接点（target handle）', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      const { container } = renderWithReactFlow(
        <NotificationNode data={mockData} id="test-node" />
      );

      // 断言：应该有 target handle
      const targetHandle = container.querySelector('.react-flow__handle-left');
      expect(targetHandle).toBeInTheDocument();
    });

    it('应该有输出连接点（source handle）', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      const { container } = renderWithReactFlow(
        <NotificationNode data={mockData} id="test-node" />
      );

      // 断言：应该有 source handle
      const sourceHandle = container.querySelector('.react-flow__handle-right');
      expect(sourceHandle).toBeInTheDocument();
    });
  });

  describe('节点状态测试', () => {
    it('选中状态应该有视觉反馈', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
      };

      const { container } = renderWithReactFlow(
        <NotificationNode data={mockData} id="test-node" selected={true} />
      );

      // 断言：Card 应该有 selected 类名
      const card = container.querySelector('.ant-card');
      expect(card).toHaveClass('selected');
    });

    it('运行状态应该有视觉反馈', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
        status: 'running',
      };

      const { container } = renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：Card 应该有 node-running 类名
      const card = container.querySelector('.ant-card');
      expect(card).toHaveClass('node-running');
    });
  });

  describe('执行结果测试', () => {
    it('应该显示发送成功的结果', () => {
      const mockData = {
        type: 'webhook',
        subject: 'Test',
        message: 'Test message',
        url: 'https://webhook.example.com',
        include_input: true,
        output: { success: true, status: 200 },
      };

      renderWithReactFlow(<NotificationNode data={mockData} id="test-node" />);

      // 断言：应该显示执行结果
      expect(screen.getByText('执行结果')).toBeInTheDocument();
      expect(screen.getByText(/success/)).toBeInTheDocument();
    });
  });
});
