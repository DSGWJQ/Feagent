/**
 * agentsApi 单元测试
 *
 * 测试目标：
 * - 验证 API 客户端是否正确调用 HTTP 请求
 * - 验证请求参数是否正确传递
 * - 验证响应数据是否正确返回
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { agentsApi } from '../agentsApi';
import request from '@/shared/utils/request';
import type { Agent, CreateAgentDto, UpdateAgentDto } from '@/shared/types';

// Mock request 模块
vi.mock('@/shared/utils/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('agentsApi', () => {
  // 每个测试前清除 Mock
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getAgents', () => {
    it('应该调用 GET /api/agents', async () => {
      // Arrange: 准备测试数据
      const mockAgents: Agent[] = [
        {
          id: '1',
          name: '测试 Agent',
          start: '起始状态',
          goal: '目标状态',
          created_at: '2024-01-15T00:00:00Z',
          updated_at: '2024-01-15T00:00:00Z',
        },
      ];
      vi.mocked(request.get).mockResolvedValue(mockAgents);

      // Act: 执行测试
      const result = await agentsApi.getAgents();

      // Assert: 验证结果
      expect(request.get).toHaveBeenCalledWith('/api/agents', { params: undefined });
      expect(result).toEqual(mockAgents);
    });

    it('应该传递查询参数', async () => {
      // Arrange
      const params = { skip: 0, limit: 10, search: 'test' };
      vi.mocked(request.get).mockResolvedValue([]);

      // Act
      await agentsApi.getAgents(params);

      // Assert
      expect(request.get).toHaveBeenCalledWith('/api/agents', { params });
    });
  });

  describe('getAgent', () => {
    it('应该调用 GET /api/agents/:id', async () => {
      // Arrange
      const mockAgent: Agent = {
        id: '1',
        name: '测试 Agent',
        start: '起始状态',
        goal: '目标状态',
        created_at: '2024-01-15T00:00:00Z',
        updated_at: '2024-01-15T00:00:00Z',
      };
      vi.mocked(request.get).mockResolvedValue(mockAgent);

      // Act
      const result = await agentsApi.getAgent('1');

      // Assert
      expect(request.get).toHaveBeenCalledWith('/api/agents/1');
      expect(result).toEqual(mockAgent);
    });
  });

  describe('createAgent', () => {
    it('应该调用 POST /api/agents', async () => {
      // Arrange
      const createData: CreateAgentDto = {
        name: '新 Agent',
        start: '起始状态',
        goal: '目标状态',
      };
      const mockAgent: Agent = {
        id: '1',
        ...createData,
        created_at: '2024-01-15T00:00:00Z',
        updated_at: '2024-01-15T00:00:00Z',
      };
      vi.mocked(request.post).mockResolvedValue(mockAgent);

      // Act
      const result = await agentsApi.createAgent(createData);

      // Assert
      expect(request.post).toHaveBeenCalledWith('/api/agents', createData);
      expect(result).toEqual(mockAgent);
    });
  });

  describe('updateAgent', () => {
    it('应该调用 PUT /api/agents/:id', async () => {
      // Arrange
      const updateData: UpdateAgentDto = {
        name: '更新后的名称',
      };
      const mockAgent: Agent = {
        id: '1',
        name: '更新后的名称',
        start: '起始状态',
        goal: '目标状态',
        created_at: '2024-01-15T00:00:00Z',
        updated_at: '2024-01-15T00:00:00Z',
      };
      vi.mocked(request.put).mockResolvedValue(mockAgent);

      // Act
      const result = await agentsApi.updateAgent('1', updateData);

      // Assert
      expect(request.put).toHaveBeenCalledWith('/api/agents/1', updateData);
      expect(result).toEqual(mockAgent);
    });
  });

  describe('deleteAgent', () => {
    it('应该调用 DELETE /api/agents/:id', async () => {
      // Arrange
      vi.mocked(request.delete).mockResolvedValue(undefined);

      // Act
      await agentsApi.deleteAgent('1');

      // Assert
      expect(request.delete).toHaveBeenCalledWith('/api/agents/1');
    });
  });
});

/**
 * 测试总结：
 *
 * ✅ 测试了所有 API 方法
 * ✅ 验证了请求参数的正确性
 * ✅ 验证了响应数据的正确性
 * ✅ 使用 Mock 避免真实的 HTTP 请求
 *
 * 为什么要测试 API 客户端？
 * 1. 确保 API 调用的正确性
 * 2. 作为 API 使用的文档
 * 3. 重构时的安全网
 */
