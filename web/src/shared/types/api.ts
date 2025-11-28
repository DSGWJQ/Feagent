/**
 * 统一响应结构
 */
export interface Result<T = any> {
  code: number;
  message: string;
  data?: T;
  detail?: string;
  trace_id?: string;
}

/**
 * 分页结果
 */
export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * 分页查询参数
 */
export interface PageParams {
  page?: number;
  page_size?: number;
  [key: string]: any;
}
