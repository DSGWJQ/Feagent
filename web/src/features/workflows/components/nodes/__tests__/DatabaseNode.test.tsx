/**
 * DatabaseNode 组件测试
 *
 * 测试策略（TDD）：
 * 1. 渲染测试：节点能正常渲染，显示标题和图标
 * 2. SQL 输入测试：SQL 文本框能正常显示和输入
 * 3. 数据库连接配置测试：数据库 URL 输入框正常工作
 * 4. 参数化查询测试：参数输入功能正常
 * 5. 连接点测试：输入和输出连接点存在
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReactFlowProvider } from '@xyflow/react';
import DatabaseNode from '../DatabaseNode';

// 包装组件（提供 ReactFlow 上下文）
const renderWithReactFlow = (ui: React.ReactElement) => {
  return render(<ReactFlowProvider>{ui}</ReactFlowProvider>);
};

describe('DatabaseNode - TDD', () => {
  describe('渲染测试', () => {
    it('应该渲染数据库节点并显示标题', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: 'SELECT * FROM users',
      };

      renderWithReactFlow(<DatabaseNode data={mockData} id="test-node" />);

      // 断言：应该显示"数据库"标题
      expect(screen.getByText('数据库')).toBeInTheDocument();
    });

    it('应该显示数据库图标', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: 'SELECT * FROM users',
      };

      renderWithReactFlow(<DatabaseNode data={mockData} id="test-node" />);

      // 断言：应该有数据库图标（通过 aria-label 或 role 查找）
      const icon = screen.getByRole('img', { hidden: true });
      expect(icon).toBeInTheDocument();
    });
  });

  describe('SQL 输入测试', () => {
    it('应该显示 SQL 展示区域', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: '',
      };

      renderWithReactFlow(<DatabaseNode data={mockData} id="test-node" />);

      // 断言：应该有"SQL 查询"标签
      expect(screen.getByText('SQL 查询')).toBeInTheDocument();
    });

    it('应该显示现有的 SQL 内容', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: 'SELECT * FROM users WHERE id = 1',
      };

      renderWithReactFlow(<DatabaseNode data={mockData} id="test-node" />);

      // 断言：应该显示 SQL 内容
      const sqlInput = screen.getByDisplayValue('SELECT * FROM users WHERE id = 1');
      expect(sqlInput).toBeInTheDocument();
    });

    it('SQL 输入框应该是只读的（配置在配置面板中完成）', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: 'SELECT * FROM users',
      };

      renderWithReactFlow(<DatabaseNode data={mockData} id="test-node" />);

      const sqlInput = screen.getByDisplayValue('SELECT * FROM users');

      // 断言：输入框应该是只读的
      expect(sqlInput).toHaveAttribute('readonly');
    });
  });

  describe('数据库连接配置测试', () => {
    it('应该显示数据库连接标签', () => {
      const mockData = {
        database_url: '',
        sql: 'SELECT 1',
      };

      renderWithReactFlow(<DatabaseNode data={mockData} id="test-node" />);

      // 断言：应该有"数据库连接"标签
      expect(screen.getByText('数据库连接')).toBeInTheDocument();
    });

    it('应该显示现有的数据库 URL', () => {
      const mockData = {
        database_url: 'postgresql://localhost:5432/mydb',
        sql: 'SELECT 1',
      };

      renderWithReactFlow(<DatabaseNode data={mockData} id="test-node" />);

      // 断言：应该显示数据库 URL
      const urlInput = screen.getByDisplayValue('postgresql://localhost:5432/mydb');
      expect(urlInput).toBeInTheDocument();
    });
  });

  describe('参数化查询测试', () => {
    it('应该显示参数输入区域', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: 'SELECT * FROM users WHERE id = ?',
        params: { id: '1' },
      };

      renderWithReactFlow(<DatabaseNode data={mockData} id="test-node" />);

      // 断言：应该有"参数"标签
      expect(screen.getByText('参数')).toBeInTheDocument();
    });

    it('应该显示现有的参数配置', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: 'SELECT * FROM users WHERE id = :userId',
        params: { userId: '123' },
      };

      renderWithReactFlow(<DatabaseNode data={mockData} id="test-node" />);

      // 断言：应该显示参数的 JSON 表示（通过 textarea 内容匹配）
      const paramsTextarea = screen.getByText('参数').nextElementSibling as HTMLTextAreaElement;
      expect(paramsTextarea).toBeTruthy();
      expect(paramsTextarea.value).toContain('userId');
      expect(paramsTextarea.value).toContain('123');
    });
  });

  describe('连接点测试', () => {
    it('应该有输入连接点（target handle）', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: 'SELECT 1',
      };

      const { container } = renderWithReactFlow(
        <DatabaseNode data={mockData} id="test-node" />
      );

      // 断言：应该有 target handle
      const targetHandle = container.querySelector('.react-flow__handle-left');
      expect(targetHandle).toBeInTheDocument();
    });

    it('应该有输出连接点（source handle）', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: 'SELECT 1',
      };

      const { container } = renderWithReactFlow(
        <DatabaseNode data={mockData} id="test-node" />
      );

      // 断言：应该有 source handle
      const sourceHandle = container.querySelector('.react-flow__handle-right');
      expect(sourceHandle).toBeInTheDocument();
    });
  });

  describe('节点状态测试', () => {
    it('选中状态应该有视觉反馈', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: 'SELECT 1',
      };

      const { container } = renderWithReactFlow(
        <DatabaseNode data={mockData} id="test-node" selected={true} />
      );

      // 断言：Card 应该有 selected 类名
      const card = container.querySelector('.ant-card');
      expect(card).toHaveClass('selected');
    });

    it('运行状态应该有视觉反馈', () => {
      const mockData = {
        database_url: 'sqlite:///test.db',
        sql: 'SELECT 1',
        status: 'running',
      };

      const { container } = renderWithReactFlow(<DatabaseNode data={mockData} id="test-node" />);

      // 断言：Card 应该有 node-running 类名
      const card = container.querySelector('.ant-card');
      expect(card).toHaveClass('node-running');
    });
  });
});
