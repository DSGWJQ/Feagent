/**
 * FileNode 组件测试
 *
 * 测试策略（TDD）：
 * 1. 渲染测试：节点能正常渲染，显示标题和图标
 * 2. 操作类型测试：操作类型选择（read/write/append/delete）
 * 3. 文件路径测试：路径输入框正常工作
 * 4. 编码配置测试：编码选择功能
 * 5. 内容显示测试：读写内容展示
 * 6. 连接点测试：输入和输出连接点存在
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import FileNode from '../FileNode';

// 包装组件（提供 ReactFlow 上下文）
const renderWithReactFlow = (ui: React.ReactElement) => {
  return render(<ReactFlowProvider>{ui}</ReactFlowProvider>);
};

describe('FileNode - TDD', () => {
  describe('渲染测试', () => {
    it('应该渲染文件节点并显示标题', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该显示"文件"标题
      expect(screen.getByText('文件')).toBeInTheDocument();
    });

    it('应该显示文件图标', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该有文件图标（通过 role 查找）
      const icon = screen.getByRole('img', { hidden: true });
      expect(icon).toBeInTheDocument();
    });
  });

  describe('操作类型测试', () => {
    it('应该显示操作类型标签', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该有"操作类型"标签
      expect(screen.getByText('操作类型')).toBeInTheDocument();
    });

    it('应该显示当前的操作类型', () => {
      const mockData = {
        operation: 'write',
        path: '/path/to/output.txt',
        encoding: 'utf-8',
        content: 'Hello World',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该显示 write 操作
      expect(screen.getByDisplayValue('write')).toBeInTheDocument();
    });

    it('操作类型应该是只读的', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      const operationInput = screen.getByDisplayValue('read');
      expect(operationInput).toHaveAttribute('readonly');
    });
  });

  describe('文件路径测试', () => {
    it('应该显示文件路径标签', () => {
      const mockData = {
        operation: 'read',
        path: '',
        encoding: 'utf-8',
        content: '',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该有"文件路径"标签
      expect(screen.getByText('文件路径')).toBeInTheDocument();
    });

    it('应该显示现有的文件路径', () => {
      const mockData = {
        operation: 'read',
        path: '/home/user/data/input.json',
        encoding: 'utf-8',
        content: '',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该显示文件路径
      const pathInput = screen.getByDisplayValue('/home/user/data/input.json');
      expect(pathInput).toBeInTheDocument();
    });

    it('文件路径应该是只读的', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      const pathInput = screen.getByDisplayValue('/path/to/file.txt');
      expect(pathInput).toHaveAttribute('readonly');
    });
  });

  describe('编码配置测试', () => {
    it('应该显示编码标签', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该有"编码"标签
      expect(screen.getByText('编码')).toBeInTheDocument();
    });

    it('应该显示当前的编码设置', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'gbk',
        content: '',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该显示 gbk 编码
      expect(screen.getByDisplayValue('gbk')).toBeInTheDocument();
    });
  });

  describe('内容显示测试', () => {
    it('write 操作应该显示内容输入区域', () => {
      const mockData = {
        operation: 'write',
        path: '/path/to/output.txt',
        encoding: 'utf-8',
        content: 'Sample content',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该有"内容"标签
      expect(screen.getByText('内容')).toBeInTheDocument();
    });

    it('应该显示要写入的内容', () => {
      const mockData = {
        operation: 'write',
        path: '/path/to/output.txt',
        encoding: 'utf-8',
        content: 'Hello, World!\nThis is a test.',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该显示内容
      const contentTextarea = screen.getByDisplayValue(/Hello, World!/);
      expect(contentTextarea).toBeInTheDocument();
    });

    it('read 操作不应该显示内容输入（由执行结果显示）', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/input.txt',
        encoding: 'utf-8',
        content: '',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：不应该有内容输入区域（read 操作的内容在 output 中）
      expect(screen.queryByText('内容')).not.toBeInTheDocument();
    });

    it('应该显示执行结果（output）', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/input.txt',
        encoding: 'utf-8',
        content: '',
        output: 'File content from read operation',
      };

      renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：应该显示输出结果
      expect(screen.getByText('执行结果')).toBeInTheDocument();
      expect(screen.getByText(/File content from read operation/)).toBeInTheDocument();
    });
  });

  describe('连接点测试', () => {
    it('应该有输入连接点（target handle）', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
      };

      const { container } = renderWithReactFlow(
        <FileNode data={mockData} id="test-node" />
      );

      // 断言：应该有 target handle
      const targetHandle = container.querySelector('.react-flow__handle-left');
      expect(targetHandle).toBeInTheDocument();
    });

    it('应该有输出连接点（source handle）', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
      };

      const { container } = renderWithReactFlow(
        <FileNode data={mockData} id="test-node" />
      );

      // 断言：应该有 source handle
      const sourceHandle = container.querySelector('.react-flow__handle-right');
      expect(sourceHandle).toBeInTheDocument();
    });
  });

  describe('节点状态测试', () => {
    it('选中状态应该有视觉反馈', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
      };

      const { container } = renderWithReactFlow(
        <FileNode data={mockData} id="test-node" selected={true} />
      );

      // 断言：Card 应该有 selected 类名
      const card = container.querySelector('.ant-card');
      expect(card).toHaveClass('selected');
    });

    it('运行状态应该有视觉反馈', () => {
      const mockData = {
        operation: 'read',
        path: '/path/to/file.txt',
        encoding: 'utf-8',
        content: '',
        status: 'running',
      };

      const { container } = renderWithReactFlow(<FileNode data={mockData} id="test-node" />);

      // 断言：Card 应该有 node-running 类名
      const card = container.querySelector('.ant-card');
      expect(card).toHaveClass('node-running');
    });
  });
});
