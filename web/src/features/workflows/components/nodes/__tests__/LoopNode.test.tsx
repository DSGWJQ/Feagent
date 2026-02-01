/**
 * LoopNode 组件测试
 *
 * 测试策略（TDD）：
 * 1. 渲染测试：节点能正��渲染，显示标题和图标
 * 2. 循环类型测试：类型选择（for_each/range/while）
 * 3. 数组配置测试：数组变量名输入
 * 4. 代码配置测试：循环体代码输入
 * 5. 范围/条件信息测试：显示 range/while 的关键参数
 * 6. 连接点测试：输入和输出连接点存在
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import LoopNode from '../LoopNode';

// 包装组件（提供 ReactFlow 上下文）
const renderWithReactFlow = (ui: React.ReactElement) => {
  return render(<ReactFlowProvider>{ui}</ReactFlowProvider>);
};

describe('LoopNode - TDD', () => {
  describe('渲染测试', () => {
    it('应该渲染循环节点并显示标题', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该显示"循环"标题
      expect(screen.getByText('循环')).toBeInTheDocument();
    });

    it('应该显示循环图标', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该有循环图标（通过 role 查找）
      const icon = screen.getByRole('img', { hidden: true });
      expect(icon).toBeInTheDocument();
    });
  });

  describe('循环类型测试', () => {
    it('应该显示循环类型标签', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该有"循环类型"标签
      expect(screen.getByText('循环类型')).toBeInTheDocument();
    });

    it('应该显示当前的循环类型', () => {
      const mockData = {
        type: 'for',
        array: 'numbers',
        code: 'sum += num',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该显示 for 类型
      expect(screen.getByDisplayValue('for')).toBeInTheDocument();
    });

    it('循环类型应该是只读的', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      const typeInput = screen.getByDisplayValue('for_each');
      expect(typeInput).toHaveAttribute('readonly');
    });
  });

  describe('数组配置测试', () => {
    it('应该显示数组变量标签', () => {
      const mockData = {
        type: 'for_each',
        array: '',
        code: 'result = item',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该有"数组变量"标签
      expect(screen.getByText('数组变量')).toBeInTheDocument();
    });

    it('应该显示现有的数组变量名', () => {
      const mockData = {
        type: 'for_each',
        array: 'userList',
        code: 'processUser(user)',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该显示数组变量名
      const arrayInput = screen.getByDisplayValue('userList');
      expect(arrayInput).toBeInTheDocument();
    });

    it('数组变量应该是只读的', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      const arrayInput = screen.getByDisplayValue('items');
      expect(arrayInput).toHaveAttribute('readonly');
    });
  });

  describe('代码配置测试', () => {
    it('应该显示循环体代码标签', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: '',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该有"循环体代码"标签
      expect(screen.getByText('循环体代码')).toBeInTheDocument();
    });

    it('应该显示循环体代码内容', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'const processed = processItem(item);\nresults.push(processed);',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该显示代码内容
      const codeTextarea = screen.getByDisplayValue(/processItem/);
      expect(codeTextarea).toBeInTheDocument();
    });

    it('循环体代码应该是只读的', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      const codeTextarea = screen.getByDisplayValue('result = item');
      expect(codeTextarea).toHaveAttribute('readonly');
    });
  });

  describe('迭代信息测试', () => {
    it('应该显示 range 的 end 值（如果有）', () => {
      const mockData = {
        type: 'range',
        start: 0,
        end: 10,
        step: 1,
        code: 'result = i',
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该显示范围信息
      expect(screen.getByText('范围')).toBeInTheDocument();
      expect(screen.getByDisplayValue('10')).toBeInTheDocument();
    });

    it('应该显示当前索引（运行时）', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
        current_index: 5,
        total: 10,
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该显示当前进度
      expect(screen.getByText(/5.*10/)).toBeInTheDocument();
    });
  });

  describe('连接点测试', () => {
    it('应该有输入连接点（target handle）', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
      };

      const { container } = renderWithReactFlow(
        <LoopNode data={mockData} id="test-node" />
      );

      // 断言：应该有 target handle
      const targetHandle = container.querySelector('.react-flow__handle-left');
      expect(targetHandle).toBeInTheDocument();
    });

    it('应该有输出连接点（source handle）', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
      };

      const { container } = renderWithReactFlow(
        <LoopNode data={mockData} id="test-node" />
      );

      // 断言：应该有 source handle
      const sourceHandle = container.querySelector('.react-flow__handle-right');
      expect(sourceHandle).toBeInTheDocument();
    });
  });

  describe('节点状态测试', () => {
    it('选中状态应该有视觉反馈', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
      };

      const { container } = renderWithReactFlow(
        <LoopNode data={mockData} id="test-node" selected={true} />
      );

      // 断言：Card 应该有 selected 类名
      const card = container.querySelector('.ant-card');
      expect(card).toHaveClass('selected');
    });

    it('运行状态应该有视觉反馈', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
        status: 'running',
      };

      const { container } = renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：Card 应该有 node-running 类名
      const card = container.querySelector('.ant-card');
      expect(card).toHaveClass('node-running');
    });
  });

  describe('执行结果测试', () => {
    it('应该显示循环执行结果', () => {
      const mockData = {
        type: 'for_each',
        array: 'items',
        code: 'result = item',
        output: [1, 2, 3, 4, 5],
      };

      renderWithReactFlow(<LoopNode data={mockData} id="test-node" />);

      // 断言：应该显示执行结果
      expect(screen.getByText('执行结果')).toBeInTheDocument();
      expect(screen.getByText(/1.*2.*3.*4.*5/)).toBeInTheDocument();
    });
  });
});
