/**
 * Axios 请求封装
 *
 * 为什么需要这个文件？
 * - 统一的请求/响应拦截
 * - 统一的错误处理
 * - 自动添加 token（如果需要）
 *
 * 修改记录：
 * - 2024-01-15: 调整响应拦截器以适配 FastAPI 后端（直接返回数据，不包装）
 */

import axios, { AxiosError, type AxiosRequestConfig } from 'axios';
import { message } from 'antd';

/**
 * 创建 axios 实例
 *
 * 为什么使用环境变量？
 * - 开发环境和生产环境的 API 地址不同
 * - 通过 .env 文件配置，避免硬编码
 *
 * 为什么开发环境 baseURL 为空？
 * - 开发环境使用 Vite 代理（vite.config.ts 中配置）
 * - 请求 /api/agents 会被代理到 http://localhost:8000/api/agents
 * - 生产环境才需要设置完整的后端地址
 */
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000, // 30 秒超时
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * 请求拦截器
 *
 * 在请求发送前执行
 * - 添加 token（如果需要）
 * - 添加其他自定义 headers
 */
request.interceptors.request.use(
  (config) => {
    // 如果需要 token 认证，取消注释以下代码
    // const token = localStorage.getItem('token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error: AxiosError) => {
    console.error('Request error:', error);
    return Promise.reject(error);
  }
);

/**
 * 响应拦截器
 *
 * 在响应返回后执行
 * - 统一处理错误
 * - 提取响应数据
 *
 * 为什么直接返回 response.data？
 * - 我们的 FastAPI 后端直接返回数据，不包装在 Result 结构中
 * - 简化前端代码，不需要每次都访问 result.data
 */
request.interceptors.response.use(
  (response) => {
    // 直接返回数据
    return response.data;
  },
  (error: AxiosError<{ detail?: string }>) => {
    // 错误处理
    if (error.response) {
      const { status, data } = error.response;

      switch (status) {
        case 400:
          message.error(data?.detail || '请求参数错误');
          break;
        case 401:
          message.error('未授权，请重新登录');
          // 可以在这里跳转到登录页
          // window.location.href = '/login';
          break;
        case 403:
          message.error('拒绝访问');
          break;
        case 404:
          message.error(data?.detail || '请求的资源不存在');
          break;
        case 500:
          message.error('服务器错误，请稍后重试');
          break;
        default:
          message.error(data?.detail || '请求失败');
      }
    } else if (error.request) {
      // 请求已发送但没有收到响应
      message.error('网络错误，请检查网络连接');
    } else {
      // 请求配置错误
      message.error('请求配置错误');
    }

    return Promise.reject(error);
  }
);

export default request;

/**
 * 导出类型化的请求方法
 *
 * 为什么需要这些方法？
 * - 提供更好的 TypeScript 类型推断
 * - 简化 API 调用代码
 */
export const get = <T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> => {
  return request.get(url, config);
};

export const post = <T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> => {
  return request.post(url, data, config);
};

export const put = <T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> => {
  return request.put(url, data, config);
};

export const del = <T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> => {
  return request.delete(url, config);
};

export const patch = <T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> => {
  return request.patch(url, data, config);
};
