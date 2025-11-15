import axios from 'axios';
import { message } from 'antd';
import type { Result } from '@/shared/types/api';

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
});

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    const result: Result = response.data;

    // 统一处理业务错误码
    if (result.code !== 2000) {
      message.error(result.message || '请求失败');
      return Promise.reject(new Error(result.message));
    }

    return result.data;
  },
  (error) => {
    // 网络错误处理
    if (error.response) {
      const status = error.response.status;
      switch (status) {
        case 401:
          message.error('未授权，请重新登录');
          // 跳转到登录页
          break;
        case 403:
          message.error('拒绝访问');
          break;
        case 404:
          message.error('请求的资源不存在');
          break;
        case 500:
          message.error('服务器错误');
          break;
        default:
          message.error(error.response.data?.message || '请求失败');
      }
    } else {
      message.error('网络错误，请检查网络连接');
    }

    return Promise.reject(error);
  }
);

export default request;

