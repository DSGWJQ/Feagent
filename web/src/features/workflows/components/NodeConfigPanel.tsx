/**
 * Node Config Panel - 节点配置面板
 *
 * 右侧抽屉，用于配置选中节点的参数
 */

import { useEffect, useMemo } from 'react';
import {
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Slider,
  Switch,
  Button,
  Space,
  Divider,
  Alert,
  Spin,
  message,
  ConfigProvider,
  theme,
} from 'antd';
import type { Edge, Node } from '@xyflow/react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { getWorkflowCapabilities } from '../api/workflowsApi';
import type { EnumFieldRequirement, WorkflowNodeCapability } from '../types/workflowCapabilities';
import type { Tool } from '@/types/workflow';

const { TextArea } = Input;

interface NodeConfigPanelProps {
  open: boolean;
  node: Node | null;
  nodes: Node[];
  edges: Edge[];
  onClose: () => void;
  onSave: (nodeId: string, data: Record<string, unknown>) => void;
}

export default function NodeConfigPanel({
  open,
  node,
  nodes,
  edges,
  onClose,
  onSave,
}: NodeConfigPanelProps) {
  const [form] = Form.useForm<Record<string, unknown>>();

  const {
    data: capabilities,
    isLoading: capabilitiesLoading,
    error: capabilitiesError,
  } = useQuery({
    queryKey: ['workflows', 'capabilities'],
    queryFn: getWorkflowCapabilities,
    enabled: open,
    staleTime: 60_000,
  });

  const nodeCapability: WorkflowNodeCapability | null = useMemo(() => {
    if (!node || !capabilities?.node_types) return null;
    return capabilities.node_types.find((item) => item.type === node.type) ?? null;
  }, [capabilities, node]);

  const validationContract = nodeCapability?.validation_contract ?? null;

  const getEnumSpec = useMemo(() => {
    return (key: string): EnumFieldRequirement | null => {
      if (!validationContract) return null;
      return validationContract.enum_fields.find((spec) => spec.key === key) ?? null;
    };
  }, [validationContract]);

  const buildEnumOptions = useMemo(() => {
    return (spec: EnumFieldRequirement | null): Array<{ value: string; label: string }> => {
      if (!spec) return [];
      const meta = spec.meta;
      const labels =
        meta && typeof meta === 'object' && meta !== null
          ? ((meta as Record<string, unknown>)['labels'] as unknown)
          : null;
      const labelMap: Record<string, string> = {};
      if (labels && typeof labels === 'object' && labels !== null) {
        for (const [k, v] of Object.entries(labels as Record<string, unknown>)) {
          if (typeof v === 'string') {
            labelMap[k] = v;
          }
        }
      }
      return (spec.allowed ?? []).map((value) => ({
        value,
        label: labelMap[value] ?? value,
      }));
    };
  }, []);

  const isToolNode = node?.type === 'tool';
  const { data: tools = [], isLoading: toolsLoading } = useQuery({
    queryKey: ['tools', 'list'],
    queryFn: async (): Promise<Tool[]> => {
      const response = await apiClient.instance.get<{ tools: Tool[] }>('/tools');
      return response.data.tools ?? [];
    },
    enabled: open && isToolNode,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (node) {
      const data = (node.data ?? {}) as Record<string, unknown>;
      const normalized: Record<string, unknown> = { ...data };

      if (node.type === 'httpRequest') {
        // Back-compat: accept legacy `path` but display it in URL input as well.
        if (!normalized.url && typeof data['path'] === 'string') {
          normalized.url = data['path'];
        }
      }

      if (node.type === 'database') {
        const params = data['params'];
        if (params && typeof params !== 'string') {
          normalized.params = JSON.stringify(params, null, 2);
        }
      }

      if (node.type === 'transform') {
        for (const key of ['mapping', 'conversions', 'fields', 'operations', 'aggregation', 'element_transform']) {
          const value = data[key];
          if (value && typeof value !== 'string') {
            normalized[key] = JSON.stringify(value, null, 2);
          }
        }
      }

      if (node.type === 'loop') {
        // Back-compat: older UI used `type=for` + `iterations`; runtime uses `range` + `end`.
        if (data['type'] === 'for') {
          normalized.type = 'range';
          if (data['end'] == null && data['iterations'] != null) {
            normalized.end = data['iterations'];
          }
          delete normalized.iterations;
        }
      }

      form.setFieldsValue({
        ...normalized,
        // Back-compat: accept legacy toolId but persist tool_id.
        tool_id: data.tool_id ?? data.toolId ?? '',
        // Back-compat: accept legacy promptSource but persist promptSourceNodeId.
        promptSourceNodeId: data.promptSourceNodeId ?? data.promptSource ?? '',
      });
    }
  }, [node, form]);

  const handleSave = async () => {
    if (capabilitiesError) {
      message.error('Capabilities 加载失败：无法保存节点配置');
      return;
    }
    try {
      // Run AntD rules (required fields, conditional UI rules, etc.).
      await form.validateFields();
    } catch {
      return;
    }

    const values = form.getFieldsValue() as Record<string, unknown>;

    if (node?.type === 'transform') {
      const jsonFields = ['mapping', 'conversions', 'fields', 'operations', 'aggregation', 'element_transform'] as const;
      for (const field of jsonFields) {
        const raw = values[field];
        if (typeof raw !== 'string') continue;
        const trimmed = raw.trim();
        if (!trimmed) {
          delete values[field];
          continue;
        }
        try {
          values[field] = JSON.parse(trimmed);
        } catch {
          message.error(`Invalid JSON in ${field}`);
          return;
        }
      }
    }

    if (node) {
      onSave(node.id, values);
      onClose();
    }
  };

  const renderConfigForm = () => {
    if (!node) return null;

    if (capabilitiesLoading) {
      return (
        <div style={{ padding: 16 }}>
          <Spin />
        </div>
      );
    }

    if (capabilitiesError || !capabilities) {
      return (
        <Alert
          type="error"
          showIcon
          message="Capabilities unavailable"
          description="无法从后端加载 /api/workflows/capabilities（fail-closed：不允许在未知能力边界下编辑配置）。"
        />
      );
    }

    if (!nodeCapability || !validationContract) {
      return (
        <Alert
          type="error"
          showIcon
          message="Unknown node type"
          description={`该节点类型未出现在 capabilities 中：${node.type}`}
        />
      );
    }

    switch (node.type) {
      case 'start':
      case 'end':
        return (
          <div style={{ padding: 16, textAlign: 'center', color: '#8c8c8c' }}>
            This node has no configuration options.
          </div>
        );

      case 'httpRequest':
        return (
          <>
            <Form.Item
              label="URL"
              name="url"
              dependencies={['path']}
              rules={[
                ({ getFieldValue }) => ({
                  validator: async (_, value) => {
                    const rawUrl = typeof value === 'string' ? value.trim() : '';
                    const rawPath = typeof getFieldValue('path') === 'string' ? (getFieldValue('path') as string).trim() : '';
                    if (rawUrl || rawPath) return;
                    const anyOf = validationContract.required_any_of.find((req) => req.keys.includes('url') || req.keys.includes('path'));
                    throw new Error(anyOf?.message || 'url (or path) is required');
                  },
                }),
              ]}
            >
              <Input placeholder="https://api.example.com" />
            </Form.Item>
            <Form.Item label="Path (legacy, optional)" name="path">
              <Input placeholder="/v1/resource" />
            </Form.Item>
            <Form.Item
              label="Method"
              name="method"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'method')?.message ||
                    'method is required',
                },
              ]}
            >
              <Select options={buildEnumOptions(getEnumSpec('method'))} />
            </Form.Item>
            <Form.Item label="Headers" name="headers">
              <TextArea
                rows={4}
                placeholder='{"Content-Type": "application/json"}'
              />
            </Form.Item>
            <Form.Item label="Body" name="body">
              <TextArea rows={4} placeholder='{"key": "value"}' />
            </Form.Item>
          </>
        );

      case 'textModel': {
        const incomingSourceIds = Array.from(
          new Set(
            edges
              .filter((edge) => edge.target === node.id)
              .map((edge) => edge.source)
              .filter(Boolean)
          )
        );

        const data = (node.data ?? {}) as Record<string, unknown>;
        const promptValue = data['prompt'] ?? data['user_prompt'];
        const hasPrompt = typeof promptValue === 'string' && promptValue.trim().length > 0;
        const requiresPromptSource = incomingSourceIds.length > 1 && !hasPrompt;

        const promptSourceOptions = incomingSourceIds.map((sourceId) => {
          const sourceNode = nodes.find((n) => n.id === sourceId);
          const sourceData = (sourceNode?.data ?? {}) as Record<string, unknown>;
          const name =
            typeof sourceData['name'] === 'string' ? sourceData['name'].trim() : '';
          const type = sourceNode?.type ?? 'node';
          return {
            value: sourceId,
            label: name ? `${name} (${type}:${sourceId})` : `${type} (${sourceId})`,
          };
        });

        return (
          <>
            <Form.Item
              label="Model"
              name="model"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'model')?.message ||
                    'model is required',
                },
              ]}
            >
              <Select options={buildEnumOptions(getEnumSpec('model'))} />
            </Form.Item>
            {requiresPromptSource ? (
              <Alert
                type="info"
                showIcon
                message="Multiple inputs detected"
                description="This textModel node has multiple incoming edges. Select which upstream node should be used as the prompt source (or add a Prompt node to merge inputs)."
                style={{ marginBottom: 12 }}
              />
            ) : null}
            {incomingSourceIds.length > 1 && !hasPrompt ? (
              <Form.Item
                label="Prompt Source"
                name="promptSourceNodeId"
                rules={[
                  {
                    required: true,
                    message: 'Please select prompt source node',
                  },
                ]}
              >
                <Select
                  placeholder="Select which upstream node provides the prompt"
                  options={promptSourceOptions}
                />
              </Form.Item>
            ) : null}
            <Form.Item label="Temperature" name="temperature">
              <Slider min={0} max={2} step={0.1} marks={{ 0: '0', 1: '1', 2: '2' }} />
            </Form.Item>
            <Form.Item label="Max Tokens" name="maxTokens">
              <InputNumber min={1} max={100000} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="Structured Output" name="structuredOutput" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item
              noStyle
              shouldUpdate={(prevValues, currentValues) =>
                prevValues.structuredOutput !== currentValues.structuredOutput
              }
            >
              {({ getFieldValue }) =>
                getFieldValue('structuredOutput') ? (
                  <>
                    <Form.Item label="Schema Name" name="schemaName">
                      <Input placeholder="MySchema" />
                    </Form.Item>
                    <Form.Item label="Schema" name="schema">
                      <TextArea
                        rows={6}
                        placeholder='{"type": "object", "properties": {...}}'
                      />
                    </Form.Item>
                  </>
                ) : null
              }
            </Form.Item>
          </>
        );
      }

      case 'embeddingModel':
        return (
          <>
            <Form.Item
              label="Model"
              name="model"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'model')?.message ||
                    'model is required',
                },
              ]}
            >
              <Select options={buildEnumOptions(getEnumSpec('model'))} />
            </Form.Item>
            <Form.Item label="Dimensions" name="dimensions">
              <InputNumber min={1} max={3072} style={{ width: '100%' }} />
            </Form.Item>
          </>
        );

      case 'imageGeneration':
        return (
          <>
            <Form.Item
              label="Model"
              name="model"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'model')?.message ||
                    'model is required',
                },
              ]}
            >
              <Select options={buildEnumOptions(getEnumSpec('model'))} />
            </Form.Item>
            <Form.Item label="Aspect Ratio" name="aspectRatio">
              <Select options={buildEnumOptions(getEnumSpec('aspectRatio'))} />
            </Form.Item>
            <Form.Item label="Output Format" name="outputFormat">
              <Select options={buildEnumOptions(getEnumSpec('outputFormat'))} />
            </Form.Item>
          </>
        );

      case 'audio':
        return (
          <>
            <Form.Item
              label="Model"
              name="model"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'model')?.message ||
                    'model is required',
                },
              ]}
            >
              <Select options={buildEnumOptions(getEnumSpec('model'))} />
            </Form.Item>
            <Form.Item label="Voice" name="voice">
              <Select options={buildEnumOptions(getEnumSpec('voice'))} />
            </Form.Item>
            <Form.Item label="Speed" name="speed">
              <Slider min={0.25} max={4.0} step={0.25} marks={{ 0.25: '0.25x', 1: '1x', 4: '4x' }} />
            </Form.Item>
          </>
        );

      case 'conditional':
        return (
          <>
            <Form.Item
              label="Condition"
              name="condition"
              rules={[{ required: true, message: 'Please enter condition' }]}
            >
              <TextArea
                rows={4}
                placeholder="input1 === 'value'"
              />
            </Form.Item>
            <Divider />
            <div style={{ fontSize: 12, color: '#8c8c8c' }}>
              <p>Available variables:</p>
              <ul style={{ paddingLeft: 20 }}>
                <li>input1, input2, ... (from connected nodes)</li>
                <li>Use JavaScript expressions</li>
              </ul>
            </div>
          </>
        );

      case 'javascript':
        return (
          <>
            <Form.Item
              label="Code"
              name="code"
              rules={[{ required: true, message: 'Please enter code' }]}
            >
              <TextArea
                rows={12}
                placeholder="// Your code here&#10;return input1;"
                style={{ fontFamily: 'monospace' }}
              />
            </Form.Item>
            <Divider />
            <div style={{ fontSize: 12, color: '#8c8c8c' }}>
              <p>Available variables:</p>
              <ul style={{ paddingLeft: 20 }}>
                <li>input1, input2, ... (from connected nodes)</li>
                <li>Must return a value</li>
              </ul>
            </div>
          </>
        );

      case 'prompt':
        return (
          <>
            <Form.Item
              label="Content"
              name="content"
              rules={[{ required: true, message: 'Please enter content' }]}
            >
              <TextArea
                rows={8}
                placeholder="Enter your prompt..."
              />
            </Form.Item>
          </>
        );

      case 'python':
        return (
          <>
            <Form.Item
              label="Code"
              name="code"
              rules={[{ required: true, message: 'Please enter code' }]}
            >
              <TextArea
                rows={12}
                placeholder="result = input1"
                style={{ fontFamily: 'monospace' }}
              />
            </Form.Item>
            <Divider />
            <div style={{ fontSize: 12, color: '#8c8c8c' }}>
              <p>Available variables:</p>
              <ul style={{ paddingLeft: 20 }}>
                <li>input1, input2, ... (from connected nodes)</li>
                <li>Assign output to a <code>result</code> variable</li>
              </ul>
            </div>
          </>
        );

      case 'transform':
        return (
          <>
            <Form.Item
              label="Type"
              name="type"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'type')?.message ||
                    'type is required',
                },
              ]}
            >
              <Select options={buildEnumOptions(getEnumSpec('type'))} />
            </Form.Item>

            <Form.Item label="field" name="field">
              <Input placeholder="e.g. items" />
            </Form.Item>

            <Form.Item label="path" name="path">
              <Input placeholder="e.g. user.profile.address.city" />
            </Form.Item>

            <Form.Item label="condition" name="condition">
              <Input placeholder="e.g. price > 100" />
            </Form.Item>

            <Form.Item label="function" name="function">
              <Input placeholder="e.g. upper / lower / len" />
            </Form.Item>

            <Form.Item label="mapping (JSON)" name="mapping">
              <TextArea rows={6} placeholder='{"newKey":"input.oldKey"}' style={{ fontFamily: 'monospace' }} />
            </Form.Item>

            <Form.Item label="conversions (JSON)" name="conversions">
              <TextArea rows={6} placeholder='{"age":"int"}' style={{ fontFamily: 'monospace' }} />
            </Form.Item>

            <Form.Item label="fields (JSON)" name="fields">
              <TextArea rows={4} placeholder='["field1","field2"]' style={{ fontFamily: 'monospace' }} />
            </Form.Item>

            <Form.Item label="operations (JSON)" name="operations">
              <TextArea rows={4} placeholder='["sum:price","count"]' style={{ fontFamily: 'monospace' }} />
            </Form.Item>

            <Form.Item label="aggregation (JSON)" name="aggregation">
              <TextArea rows={4} placeholder='{"field":"items","operations":["count"]}' style={{ fontFamily: 'monospace' }} />
            </Form.Item>

            <Form.Item label="element_transform (JSON)" name="element_transform">
              <TextArea rows={4} placeholder='{"mapping":{"a":"b"}}' style={{ fontFamily: 'monospace' }} />
            </Form.Item>
          </>
        );

      case 'database':
        return (
          <>
            <Form.Item
              label="Database URL"
              name="database_url"
              rules={[{ required: true, message: 'Please enter database URL' }]}
            >
              <Input placeholder="sqlite:///agent_data.db" />
            </Form.Item>
            <Form.Item
              label="SQL"
              name="sql"
              rules={[{ required: true, message: 'Please enter SQL' }]}
            >
              <TextArea rows={6} placeholder="SELECT 1" style={{ fontFamily: 'monospace' }} />
            </Form.Item>
            <Form.Item label="Params (JSON, optional)" name="params">
              <TextArea rows={4} placeholder="{} or []" style={{ fontFamily: 'monospace' }} />
            </Form.Item>
          </>
        );

      case 'file':
        return (
          <>
            <Form.Item
              label="Operation"
              name="operation"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'operation')?.message ||
                    'operation is required',
                },
              ]}
            >
              <Select options={buildEnumOptions(getEnumSpec('operation'))} />
            </Form.Item>
            <Form.Item
              label="Path"
              name="path"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'path')?.message ||
                    'path is required',
                },
              ]}
            >
              <Input placeholder="tmp/report.txt" />
            </Form.Item>
            <Form.Item label="Encoding" name="encoding">
              <Input placeholder="utf-8" />
            </Form.Item>
            <Form.Item label="Content" name="content">
              <TextArea rows={6} placeholder="Write/append content" />
            </Form.Item>
          </>
        );

      case 'notification':
        return (
          <>
            <Form.Item
              label="Type"
              name="type"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'type')?.message ||
                    'type is required',
                },
              ]}
            >
              <Select options={buildEnumOptions(getEnumSpec('type'))} />
            </Form.Item>
            <Form.Item label="Subject" name="subject">
              <Input placeholder="Notification" />
            </Form.Item>
            <Form.Item
              label="Message"
              name="message"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'message')?.message ||
                    'message is required',
                },
              ]}
            >
              <TextArea rows={6} placeholder="Your message here" />
            </Form.Item>
            <Form.Item label="Webhook URL" name="url">
              <Input placeholder="https://webhook.example.com" />
            </Form.Item>
            <Form.Item label="Headers (JSON)" name="headers">
              <TextArea rows={4} placeholder='{"Content-Type":"application/json"}' style={{ fontFamily: 'monospace' }} />
            </Form.Item>
            <Form.Item label="Include Input" name="include_input" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Divider />
            <Form.Item label="SMTP Host" name="smtp_host">
              <Input placeholder="smtp.example.com" />
            </Form.Item>
            <Form.Item label="SMTP Port" name="smtp_port">
              <InputNumber min={1} max={65535} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="Sender" name="sender">
              <Input placeholder="no-reply@example.com" />
            </Form.Item>
            <Form.Item label="Sender Password" name="sender_password">
              <Input.Password />
            </Form.Item>
            <Form.Item label="Recipients (JSON)" name="recipients">
              <TextArea rows={3} placeholder='["a@x.com"]' style={{ fontFamily: 'monospace' }} />
            </Form.Item>
            <Divider />
            <Form.Item label="Slack Webhook URL" name="webhook_url">
              <Input placeholder="https://hooks.slack.com/services/..." />
            </Form.Item>
          </>
        );

      case 'loop':
        return (
          <>
            <Form.Item
              label="Type"
              name="type"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'type')?.message ||
                    'type is required',
                },
              ]}
            >
              <Select options={buildEnumOptions(getEnumSpec('type'))} />
            </Form.Item>
            <Form.Item
              noStyle
              shouldUpdate={(prevValues, currentValues) => prevValues.type !== currentValues.type}
            >
              {({ getFieldValue }) => {
                const type = getFieldValue('type');
                if (type === 'for_each') {
                  return (
                    <>
                      <Form.Item
                        label="Array"
                        name="array"
                        rules={[{ required: true, message: 'Please enter array field' }]}
                      >
                        <Input placeholder="items" />
                      </Form.Item>
                      <Form.Item label="Skip None" name="skip_none" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                      <Form.Item label="Code (optional)" name="code">
                        <TextArea
                          rows={10}
                          placeholder="result = item"
                          style={{ fontFamily: 'monospace' }}
                        />
                      </Form.Item>
                    </>
                  );
                }
                if (type === 'range') {
                  return (
                    <>
                      <Form.Item label="Start" name="start">
                        <InputNumber style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        label="End"
                        name="end"
                        rules={[{ required: true, message: 'Please enter end' }]}
                      >
                        <InputNumber min={0} max={1000000} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item label="Step" name="step">
                        <InputNumber min={1} max={1000000} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        label="Code"
                        name="code"
                        rules={[{ required: true, message: 'Please enter code' }]}
                      >
                        <TextArea
                          rows={10}
                          placeholder="result = i"
                          style={{ fontFamily: 'monospace' }}
                        />
                      </Form.Item>
                    </>
                  );
                }
                if (type === 'while') {
                  return (
                    <>
                      <Form.Item
                        label="Condition"
                        name="condition"
                        rules={[{ required: true, message: 'Please enter condition' }]}
                      >
                        <TextArea
                          rows={4}
                          placeholder="iteration < 10"
                          style={{ fontFamily: 'monospace' }}
                        />
                      </Form.Item>
                      <Form.Item
                        label="Max Iterations"
                        name="max_iterations"
                        rules={[{ required: true, message: 'Please enter max_iterations' }]}
                      >
                        <InputNumber min={1} max={1000000} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        label="Code"
                        name="code"
                        rules={[{ required: true, message: 'Please enter code' }]}
                      >
                        <TextArea
                          rows={10}
                          placeholder="result = iteration"
                          style={{ fontFamily: 'monospace' }}
                        />
                      </Form.Item>
                    </>
                  );
                }
                return null;
              }}
            </Form.Item>
          </>
        );

      case 'tool':
        return (
          <>
            {!toolsLoading && tools.length === 0 ? (
              <Alert
                type="warning"
                showIcon
                message="No tools available"
                description="Create a tool in the tool library first, then select it here."
                style={{ marginBottom: 12 }}
              />
            ) : null}
            <Form.Item
              label="Tool"
              name="tool_id"
              rules={[{ required: true, message: 'Please select a tool' }]}
            >
              <Select
                showSearch
                placeholder="Select a tool from library"
                loading={toolsLoading}
                optionFilterProp="label"
                notFoundContent={toolsLoading ? 'Loading...' : 'No tools found'}
                options={tools.map((tool) => ({
                  value: tool.id,
                  label: `${tool.name} (${tool.id})`,
                }))}
                onChange={(toolId) => {
                  const selected = tools.find((tool) => tool.id === toolId);
                  if (!selected) return;
                  // Keep display fields in data for node renderers/UI, but backend validation is ID-based.
                  form.setFieldsValue({
                    name: selected.name,
                    description: selected.description ?? '',
                  });
                }}
              />
            </Form.Item>
          </>
        );

      case 'structuredOutput':
        return (
          <>
            <Form.Item
              label="Schema Name"
              name="schemaName"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'schemaName')?.message ||
                    'schemaName is required',
                },
              ]}
            >
              <Input placeholder="MySchema" />
            </Form.Item>
            <Form.Item label="Mode" name="mode">
              <Select options={buildEnumOptions(getEnumSpec('mode'))} />
            </Form.Item>
            <Form.Item
              label="Schema"
              name="schema"
              rules={[
                {
                  required: true,
                  message:
                    validationContract.required_fields.find((r) => r.key === 'schema')?.message ||
                    'schema is required',
                },
              ]}
            >
              <TextArea
                rows={10}
                placeholder='{"type": "object", "properties": {...}}'
                style={{ fontFamily: 'monospace' }}
              />
            </Form.Item>
          </>
        );

      default:
        return (
          <div style={{ padding: 16, textAlign: 'center', color: '#8c8c8c' }}>
            Unknown node type: {node.type}
          </div>
        );
    }
  };

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorBgContainer: '#141414',
          colorBgElevated: '#1a1a1a',
          colorBorder: '#262626',
          colorText: '#fafafa',
          colorTextSecondary: '#8c8c8c',
          colorPrimary: '#8b5cf6',
        },
      }}
    >
      <Drawer
        title={
          <span style={{ fontFamily: 'var(--font-family-serif)', color: 'var(--neo-gold)' }}>
            {node ? `Configure ${node.type}` : 'Configuration'}
          </span>
        }
        placement="right"
        width={480}
        open={open}
        onClose={onClose}
        styles={{
          header: {
            backgroundColor: 'var(--neo-surface)',
            borderBottom: '1px solid var(--neo-border)',
            color: 'var(--neo-text)',
          },
          body: {
            backgroundColor: 'var(--neo-bg)',
            color: 'var(--neo-text)',
          },
        }}
        extra={
          <Space>
            <Button
              onClick={onClose}
              style={{
                backgroundColor: 'transparent',
                borderColor: 'var(--neo-border)',
                color: 'var(--neo-text-2)',
              }}
            >
              Cancel
            </Button>
            <Button
              type="primary"
              onClick={handleSave}
              disabled={Boolean(capabilitiesError) || capabilitiesLoading}
              style={{
                background: 'var(--neo-gold)',
                borderColor: 'var(--neo-gold)',
                color: '#000',
              }}
            >
              Save Changes
            </Button>
          </Space>
        }
      >
        <Form
          form={form}
          layout="vertical"
          style={{
            color: 'var(--neo-text)',
          }}
        >
          {renderConfigForm()}
        </Form>
      </Drawer>
    </ConfigProvider>
  );
}
