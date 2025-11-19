/**
 * FakeAIChat 组件测试
 *
 * 测试策略：
 * 1. 渲染测试：组件能正常渲染
 * 2. 消息发送测试：用户能发送消息
 * 3. AI回复测试：AI能根据规则自动回复
 * 4. 规则匹配测试：测试不同规则的匹配和优先级
 * 5. 边界情况测试：空消息、特殊字符等
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FakeAIChat } from '../FakeAIChat';
import type { AIReplyRule } from '@/shared/types/chat';

describe('FakeAIChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('渲染测试', () => {
    it('应该正常渲染聊天界面', () => {
      // Act
      render(<FakeAIChat />);

      // Assert
      expect(screen.getByPlaceholderText(/输入消息/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /发送/i })).toBeInTheDocument();
    });

    it('应该显示初始欢迎消息', () => {
      // Act
      render(<FakeAIChat showWelcome={true} />);

      // Assert
      expect(screen.getByText(/你好/i)).toBeInTheDocument();
    });
  });

  describe('消息发送测试', () => {
    it('应该能发送用户消息', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<FakeAIChat />);

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.type(input, '你好');
      await user.click(sendButton);

      // Assert
      await waitFor(() => {
        expect(screen.getByText('你好')).toBeInTheDocument();
      });
    });

    it('发送消息后应该清空输入框', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<FakeAIChat />);

      const input = screen.getByPlaceholderText(/输入消息/i) as HTMLTextAreaElement;
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.type(input, '测试消息');
      await user.click(sendButton);

      // Assert
      await waitFor(() => {
        expect(input.value).toBe('');
      });
    });

    it('应该支持按Enter键发送消息', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<FakeAIChat />);

      const input = screen.getByPlaceholderText(/输入消息/i);

      // Act
      await user.type(input, '测试消息{Enter}');

      // Assert
      await waitFor(() => {
        expect(screen.getByText('测试消息')).toBeInTheDocument();
      });
    });

    it('不应该发送空消息', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<FakeAIChat />);

      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.click(sendButton);

      // Assert
      // 不应该有任何消息显示（除了可能的欢迎消息）
      const messages = screen.queryAllByRole('article');
      expect(messages.length).toBe(0);
    });
  });

  describe('AI回复测试', () => {
    it('应该在用户发送消息后自动回复', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<FakeAIChat />);

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.type(input, '你好');
      await user.click(sendButton);

      // Assert - 应该有AI的回复
      await waitFor(() => {
        const messages = screen.getAllByRole('article');
        expect(messages.length).toBeGreaterThanOrEqual(2); // 至少有用户消息和AI回复
      });
    });

    it('应该根据关键词匹配规则回复', async () => {
      // Arrange
      const user = userEvent.setup();
      const customRules: AIReplyRule[] = [
        {
          pattern: /天气/,
          reply: '今天天气不错！',
          priority: 100, // 设置高优先级
        },
      ];
      render(<FakeAIChat customRules={customRules} />);

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.type(input, '今天天气怎么样？');
      await user.click(sendButton);

      // Assert
      await waitFor(() => {
        expect(screen.getByText('今天天气不错！')).toBeInTheDocument();
      });
    });

    it('应该支持函数类型的回复', async () => {
      // Arrange
      const user = userEvent.setup();
      const customRules: AIReplyRule[] = [
        {
          pattern: /我叫(.+)/,
          reply: (match) => `你好，${match?.[1]}！`,
          priority: 100, // 设置高优先级
        },
      ];
      render(<FakeAIChat customRules={customRules} />);

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.type(input, '我叫张三');
      await user.click(sendButton);

      // Assert - 等待AI回复完成（不再显示"正在输入..."）
      await waitFor(
        () => {
          expect(screen.queryByText('正在输入...')).not.toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      // 然后检查回复内容
      expect(screen.getByText('你好，张三！')).toBeInTheDocument();
    });

    it('应该按优先级匹配规则', async () => {
      // Arrange
      const user = userEvent.setup();
      const customRules: AIReplyRule[] = [
        {
          pattern: /.*/,
          reply: '默认回复',
          priority: 1,
        },
        {
          pattern: /你好/,
          reply: '你好啊！',
          priority: 10,
        },
      ];
      render(<FakeAIChat customRules={customRules} />);

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.type(input, '你好');
      await user.click(sendButton);

      // Assert - 应该匹配高优先级的规则
      await waitFor(() => {
        expect(screen.getByText('你好啊！')).toBeInTheDocument();
        expect(screen.queryByText('默认回复')).not.toBeInTheDocument();
      });
    });

    it('没有匹配规则时应该使用默认回复', async () => {
      // Arrange
      const user = userEvent.setup();
      const customRules: AIReplyRule[] = [
        {
          pattern: /特定关键词/,
          reply: '特定回复',
        },
      ];
      render(<FakeAIChat customRules={customRules} />);

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.type(input, '随便说点什么');
      await user.click(sendButton);

      // Assert - 等待AI回复完成
      await waitFor(
        () => {
          expect(screen.queryByText('正在输入...')).not.toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      // 应该有默认回复
      const messages = screen.getAllByRole('article');
      expect(messages.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('回调函数测试', () => {
    it('应该在发送消息时调用onMessageSent回调', async () => {
      // Arrange
      const user = userEvent.setup();
      const onMessageSent = vi.fn();
      render(<FakeAIChat onMessageSent={onMessageSent} />);

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.type(input, '测试消息');
      await user.click(sendButton);

      // Assert
      await waitFor(() => {
        expect(onMessageSent).toHaveBeenCalledWith(
          expect.objectContaining({
            role: 'user',
            content: '测试消息',
          })
        );
      });
    });

    it('应该在AI回复时调用onAIReply回调', async () => {
      // Arrange
      const user = userEvent.setup();
      const onAIReply = vi.fn();
      render(<FakeAIChat onAIReply={onAIReply} />);

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.type(input, '你好');
      await user.click(sendButton);

      // Assert - 等待AI回复完成
      await waitFor(
        () => {
          expect(onAIReply).toHaveBeenCalledWith(
            expect.objectContaining({
              role: 'assistant',
            })
          );
        },
        { timeout: 3000 }
      );
    });
  });

  describe('边界情况测试', () => {
    it('应该处理特殊字符', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<FakeAIChat />);

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // Act
      await user.type(input, '<script>alert("xss")</script>');
      await user.click(sendButton);

      // Assert - 应该正常显示，不执行脚本
      await waitFor(() => {
        expect(screen.getByText('<script>alert("xss")</script>')).toBeInTheDocument();
      });
    });

    it('应该处理长消息', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<FakeAIChat />);

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });
      const longMessage = '这是一条很长的消息'.repeat(50);

      // Act - 使用 paste 而不是 type 来加快速度
      await user.click(input);
      await user.paste(longMessage);
      await user.click(sendButton);

      // Assert
      await waitFor(() => {
        expect(screen.getByText(longMessage)).toBeInTheDocument();
      });
    });
  });
});

