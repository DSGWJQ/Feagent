/**
 * CORS 跨域测试
 *
 * 测试目的：
 * 1. 验证前端可以成功访问后端 API
 * 2. 验证 CORS 配置是否正确
 * 3. 验证请求头是否正确设置
 *
 * 为什么需要这个测试？
 * - 跨域问题是前后端分离开发中最常见的问题
 * - 提前发现配置问题，避免浪费时间调试
 * - 确保开发环境和生产环境的配置一致
 *
 * 注意：这些测试需要后端服务运行，因此默认跳过
 * 运行方式：pnpm test -- cors.test.ts
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { agentsApi } from '@/features/agents/api/agentsApi';

describe.skip('CORS 跨域测试', () => {
  /**
   * 测试前检查
   *
   * 为什么需要这个检查？
   * - 确保后端服务正在运行
   * - 避免因为后端未启动导致测试失败
   */
  beforeAll(async () => {
    try {
      // 尝试访问后端健康检查接口
      const response = await fetch('http://localhost:8000/health');
      if (!response.ok) {
        console.warn('⚠️ 后端服务可能未正常运行，测试可能失败');
      }
    } catch (error) {
      console.warn('⚠️ 无法连接到后端服务 (http://localhost:8000)，请确保后端服务已启动');
      console.warn('   启动命令：uvicorn src.interfaces.api.main:app --reload --port 8000');
    }
  });

  it('应该能够访问后端健康检查接口', async () => {
    // 使用原生 fetch 测试，避免 axios 拦截器的影响
    const response = await fetch('http://localhost:8000/health');

    expect(response.ok).toBe(true);
    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('status');
    expect(data.status).toBe('healthy');
  }, 10000); // 10 秒超时

  it('应该能够获取 Agent 列表（测试 CORS）', async () => {
    // 使用 agentsApi 测试，验证完整的请求流程
    const agents = await agentsApi.getAgents();

    // 验证返回的数据结构
    expect(Array.isArray(agents)).toBe(true);
  }, 10000);

  it('响应头应该包含 CORS 相关字段', async () => {
    // 使用原生 fetch 测试，检查响应头
    const response = await fetch('http://localhost:8000/health');

    // 检查 CORS 响应头
    const accessControlAllowOrigin = response.headers.get('access-control-allow-origin');

    // 后端应该返回允许的源
    // 注意：如果后端配置了多个源，可能返回请求的源或 *
    expect(accessControlAllowOrigin).toBeTruthy();

    console.log('✅ CORS 响应头:', {
      'access-control-allow-origin': accessControlAllowOrigin,
      'access-control-allow-credentials': response.headers.get('access-control-allow-credentials'),
      'access-control-allow-methods': response.headers.get('access-control-allow-methods'),
      'access-control-allow-headers': response.headers.get('access-control-allow-headers'),
    });
  }, 10000);

  it('应该能够发送 POST 请求（测试预检请求）', async () => {
    // POST 请求会触发 CORS 预检请求（OPTIONS）
    // 这是测试 CORS 配置最全面的方式

    const testData = {
      start: '测试 CORS 配置 - 这是一个测试用的起点描述，用于验证跨域请求是否正常工作',
      goal: '测试 CORS 配置 - 这是一个测试用的目标描述，用于验证跨域请求是否正常工作',
      name: `CORS 测试 ${new Date().toISOString()}`,
    };

    try {
      const agent = await agentsApi.createAgent(testData);

      // 验证创建成功
      expect(agent).toHaveProperty('id');
      expect(agent.start).toBe(testData.start);
      expect(agent.goal).toBe(testData.goal);

      // 清理：删除测试数据
      await agentsApi.deleteAgent(agent.id);

      console.log('✅ POST 请求成功，CORS 配置正确');
    } catch (error: any) {
      // 如果失败，检查是否是 CORS 错误
      if (error.message?.includes('CORS') || error.message?.includes('cross-origin')) {
        throw new Error('CORS 配置错误：' + error.message);
      }
      throw error;
    }
  }, 15000);
});

/**
 * 如何运行这个测试？
 *
 * 1. 确保后端服务正在运行：
 *    cd d:\My_Project\agent_data
 *    uvicorn src.interfaces.api.main:app --reload --port 8000
 *
 * 2. 运行测试：
 *    cd web
 *    npm test -- cors.test.ts --run
 *
 * 如果测试失败，可能的原因：
 * 1. 后端服务未启动
 * 2. 后端 CORS 配置错误
 * 3. 前端 API 地址配置错误
 * 4. 网络问题
 */
