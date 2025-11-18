/**
 * CreateAgentForm - 创建 Agent 表单组件
 *
 * 功能：
 * 1. 提供三个字段：start（起点）、goal（目的）、name（名称）
 * 2. 前端验证：必填、长度限制
 * 3. 调用后端 API 创建 Agent
 * 4. 显示加载状态和错误信息
 *
 * 使用示例：
 * ```tsx
 * <CreateAgentForm
 *   onSuccess={(agent) => navigate(`/agents/${agent.id}`)}
 * />
 * ```
 */

import { Form, Input, Button, message } from 'antd';
import { useCreateAgent } from '@/shared/hooks';
import type { CreateAgentDto, Agent } from '@/shared/types';

const { TextArea } = Input;

/**
 * 表单字段类型
 *
 * 为什么和 CreateAgentDto 一样？
 * - 表单的数据结构和 API 请求的数据结构一致
 * - 可以直接将表单值传给 API
 */
interface FormValues {
  start: string;
  goal: string;
  name?: string;
}

interface CreateAgentFormProps {
  /** 创建成功后的回调 */
  onSuccess?: (agent: Agent) => void;

  /** 创建失败后的回调 */
  onError?: (error: any) => void;
}

export const CreateAgentForm: React.FC<CreateAgentFormProps> = ({
  onSuccess,
  onError,
}) => {
  const [form] = Form.useForm<FormValues>();
  const createAgent = useCreateAgent();

  /**
   * 表单提交处理
   *
   * 流程：
   * 1. 表单验证通过
   * 2. 调用 API 创建 Agent
   * 3. 成功：调用 onSuccess 回调，重置表单
   * 4. 失败：调用 onError 回调（如果提供）
   */
  const handleSubmit = async (values: FormValues) => {
    try {
      // 调用 API 创建 Agent
      const agent = await createAgent.mutateAsync(values);

      // 重置表单
      form.resetFields();

      // 调用成功回调
      onSuccess?.(agent);
    } catch (error) {
      // 调用失败回调
      onError?.(error);
    }
  };

  return (
    <Form<FormValues>
      form={form}
      layout="vertical"
      onFinish={handleSubmit}
      autoComplete="off"
    >
      {/* 起点字段 */}
      <Form.Item
        label="起点（当前状态）"
        name="start"
        rules={[
          { required: true, message: '起点描述是必填项' },
          { min: 10, message: '起点描述至少需要 10 个字符' },
          { max: 500, message: '起点描述最多 500 个字符' },
          {
            validator: (_, value) => {
              if (value && value.trim().length === 0) {
                return Promise.reject(new Error('起点描述不能只包含空格'));
              }
              return Promise.resolve();
            },
          },
        ]}
      >
        <TextArea
          placeholder="描述当前的状态或拥有的资源，例如：我有一个 CSV 文件，包含过去一年的销售数据"
          rows={4}
          showCount
          maxLength={500}
        />
      </Form.Item>

      {/* 目的字段 */}
      <Form.Item
        label="目的（期望结果）"
        name="goal"
        rules={[
          { required: true, message: '目的描述是必填项' },
          { min: 10, message: '目的描述至少需要 10 个字符' },
          { max: 500, message: '目的描述最多 500 个字符' },
          {
            validator: (_, value) => {
              if (value && value.trim().length === 0) {
                return Promise.reject(new Error('目的描述不能只包含空格'));
              }
              return Promise.resolve();
            },
          },
        ]}
      >
        <TextArea
          placeholder="描述期望达到的目标或结果，例如：分析销售数据，找出销售趋势和热门产品，生成可视化报告"
          rows={4}
          showCount
          maxLength={500}
        />
      </Form.Item>

      {/* 名称字段（可选） */}
      <Form.Item
        label="名称（可选）"
        name="name"
        rules={[
          { max: 100, message: 'Agent 名称最多 100 个字符' },
        ]}
        tooltip="不填写时，系统会根据起点和目的自动生成名称"
      >
        <Input
          placeholder="例如：销售分析 Agent"
          showCount
          maxLength={100}
        />
      </Form.Item>

      {/* 提交按钮 */}
      <Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          loading={createAgent.isPending}
          block
        >
          创建 Agent
        </Button>
      </Form.Item>
    </Form>
  );
};

/**
 * 为什么使用 Ant Design Form？
 *
 * 优点：
 * 1. 自动表单验证：rules 配置即可
 * 2. 自动错误显示：验证失败自动显示错误信息
 * 3. 自动收集表单值：onFinish 自动传入表单值
 * 4. 自动管理表单状态：touched, dirty, validating
 * 5. 支持字段联动：可以根据其他字段的值动态改变验证规则
 *
 * 为什么使用 TextArea 而不是 Input？
 * - start 和 goal 可能比较长（最多 500 字符）
 * - TextArea 提供更好的输入体验
 * - 支持多行显示
 *
 * 为什么使用 showCount？
 * - 让用户知道还能输入多少字符
 * - 避免超过长度限制
 *
 * 为什么 name 字段有 tooltip？
 * - 解释为什么这个字段是可选的
 * - 告诉用户不填写会发生什么
 *
 * 为什么提交按钮有 loading 状态？
 * - 防止重复提交
 * - 给用户反馈（正在处理中）
 * - 提升用户体验
 */
