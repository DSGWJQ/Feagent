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

import { Form, Input, Button, App } from 'antd';
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
  const { message } = App.useApp();

  /**
   * 表单提交处理
   *
   * 流程：
   * 1. 表单验证通过
   * 2. 显示 Loading 提示（AI 生成工作流中...）
   * 3. 调用 API 创建 Agent
   * 4. 成功：
   *    - 检查是否有 workflow_id
   *    - 如果有：显示成功提示，跳转到 Workflow 编辑器
   *    - 如果没有：显示警告，降级处理
   *    - 调用 onSuccess 回调，重置表单
   * 5. 失败：显示详细错误信息，支持重试
   */
  const handleSubmit = async (values: FormValues) => {
    // 显示 Loading 提示
    const loadingMessage = message.loading({
      content: 'AI 正在为您生成智能工作流，请稍候...',
      duration: 0, // 不自动关闭
    });

    try {
      // 调用 API 创建 Agent（后端自动生成 Workflow）
      const agent = await createAgent.mutateAsync(values);

      // 关闭 Loading 提示
      loadingMessage();

      // 重置表单
      form.resetFields();

      // 检查是否有 workflow_id（Agent 创建时自动生成）
      if (agent.workflow_id) {
        // 成功生成 Workflow：显示成功提示并跳转
        message.success({
          content: `Agent 创建成功！已自动生成 ${agent.tasks?.length || 0} 个任务节点，正在跳转到编辑器...`,
          duration: 2,
        });

        // 延迟跳转，让用户看到成功提示
        setTimeout(() => {
          window.location.href = `/workflows/${agent.workflow_id}/edit`;
        }, 500);
      } else {
        // 降级：Workflow 生成失败，但 Agent 创建成功
        message.warning({
          content: 'Agent 已创建，但工作流生成失败。您可以稍后手动创建工作流。',
          duration: 5,
        });
      }

      // 调用成功回调
      onSuccess?.(agent);
    } catch (error) {
      // 关闭 Loading 提示
      loadingMessage();

      // 解析错误信息
      const errorMessage =
        (error as any)?.response?.data?.detail ||
        (error as Error).message ||
        '创建失败，请检查网络连接后重试';

      // 显示错误提示（支持重试）
      message.error({
        content: `创建失败：${errorMessage}`,
        duration: 5,
      });

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
