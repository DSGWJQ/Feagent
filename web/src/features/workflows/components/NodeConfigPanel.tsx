/**
 * Node Config Panel - 节点配置面板
 *
 * 右侧抽屉，用于配置选中节点的参数
 */

import { useEffect } from 'react';
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
  message,
  ConfigProvider,
  theme,
} from 'antd';
import type { Node } from '@xyflow/react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import type { Tool } from '@/types/workflow';

const { TextArea } = Input;
const { Option } = Select;

interface NodeConfigPanelProps {
  open: boolean;
  node: Node | null;
  onClose: () => void;
  onSave: (nodeId: string, data: any) => void;
}

export default function NodeConfigPanel({
  open,
  node,
  onClose,
  onSave,
}: NodeConfigPanelProps) {
  const [form] = Form.useForm();

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
      const data = (node.data ?? {}) as any;
      const normalized: Record<string, unknown> = { ...data };

      if (node.type === 'database' && data.params && typeof data.params !== 'string') {
        normalized.params = JSON.stringify(data.params, null, 2);
      }

      if (node.type === 'transform') {
        for (const key of ['mapping', 'conversions', 'fields', 'operations', 'aggregation', 'element_transform']) {
          const value = data[key];
          if (value && typeof value !== 'string') {
            normalized[key] = JSON.stringify(value, null, 2);
          }
        }
      }

      form.setFieldsValue({
        ...normalized,
        // Back-compat: accept legacy toolId but persist tool_id.
        tool_id: data.tool_id ?? data.toolId ?? '',
      });
    }
  }, [node, form]);

  const handleSave = () => {
    const values = form.getFieldsValue() as Record<string, any>;

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
        } catch (err) {
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
              rules={[{ required: true, message: 'Please enter URL' }]}
            >
              <Input placeholder="https://api.example.com" />
            </Form.Item>
            <Form.Item
              label="Method"
              name="method"
              rules={[{ required: true, message: 'Please select method' }]}
            >
              <Select>
                <Option value="GET">GET</Option>
                <Option value="POST">POST</Option>
                <Option value="PUT">PUT</Option>
                <Option value="DELETE">DELETE</Option>
                <Option value="PATCH">PATCH</Option>
              </Select>
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

      case 'textModel':
        return (
          <>
            <Form.Item
              label="Model"
              name="model"
              rules={[{ required: true, message: 'Please select model' }]}
            >
              <Select>
                <Option value="openai/gpt-5">OpenAI GPT-5</Option>
                <Option value="openai/gpt-4">OpenAI GPT-4</Option>
                <Option value="anthropic/claude-3.5-sonnet">
                  Claude 3.5 Sonnet
                </Option>
                <Option value="google/gemini-2.5-flash">Gemini 2.5 Flash</Option>
              </Select>
            </Form.Item>
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

      case 'embeddingModel':
        return (
          <>
            <Form.Item
              label="Model"
              name="model"
              rules={[{ required: true, message: 'Please select model' }]}
            >
              <Select>
                <Option value="openai/text-embedding-3-small">
                  OpenAI Text Embedding 3 Small
                </Option>
                <Option value="openai/text-embedding-3-large">
                  OpenAI Text Embedding 3 Large
                </Option>
              </Select>
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
              rules={[{ required: true, message: 'Please select model' }]}
            >
              <Select>
                <Option value="gemini-2.5-flash-image">Gemini 2.5 Flash Image</Option>
                <Option value="openai/dall-e-3">DALL-E 3</Option>
              </Select>
            </Form.Item>
            <Form.Item label="Aspect Ratio" name="aspectRatio">
              <Select>
                <Option value="1:1">1:1 (Square)</Option>
                <Option value="16:9">16:9 (Landscape)</Option>
                <Option value="9:16">9:16 (Portrait)</Option>
              </Select>
            </Form.Item>
            <Form.Item label="Output Format" name="outputFormat">
              <Select>
                <Option value="png">PNG</Option>
                <Option value="jpg">JPG</Option>
                <Option value="webp">WebP</Option>
              </Select>
            </Form.Item>
          </>
        );

      case 'audio':
        return (
          <>
            <Form.Item
              label="Model"
              name="model"
              rules={[{ required: true, message: 'Please select model' }]}
            >
              <Select>
                <Option value="openai/tts-1">OpenAI TTS-1</Option>
                <Option value="openai/tts-1-hd">OpenAI TTS-1 HD</Option>
              </Select>
            </Form.Item>
            <Form.Item label="Voice" name="voice">
              <Select>
                <Option value="alloy">Alloy</Option>
                <Option value="echo">Echo</Option>
                <Option value="fable">Fable</Option>
                <Option value="onyx">Onyx</Option>
                <Option value="nova">Nova</Option>
                <Option value="shimmer">Shimmer</Option>
              </Select>
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
              rules={[{ required: true, message: 'Please select transform type' }]}
            >
              <Select>
                <Option value="field_mapping">field_mapping</Option>
                <Option value="type_conversion">type_conversion</Option>
                <Option value="field_extraction">field_extraction</Option>
                <Option value="array_mapping">array_mapping</Option>
                <Option value="filtering">filtering</Option>
                <Option value="aggregation">aggregation</Option>
                <Option value="custom">custom</Option>
              </Select>
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
              rules={[{ required: true, message: 'Please select operation' }]}
            >
              <Select>
                <Option value="read">read</Option>
                <Option value="write">write</Option>
                <Option value="append">append</Option>
                <Option value="delete">delete</Option>
                <Option value="list">list</Option>
              </Select>
            </Form.Item>
            <Form.Item
              label="Path"
              name="path"
              rules={[{ required: true, message: 'Please enter file path' }]}
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
              rules={[{ required: true, message: 'Please select notification type' }]}
            >
              <Select>
                <Option value="webhook">webhook</Option>
                <Option value="email">email</Option>
                <Option value="slack">slack</Option>
              </Select>
            </Form.Item>
            <Form.Item label="Subject" name="subject">
              <Input placeholder="Notification" />
            </Form.Item>
            <Form.Item
              label="Message"
              name="message"
              rules={[{ required: true, message: 'Please enter message' }]}
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
              rules={[{ required: true, message: 'Please select loop type' }]}
            >
              <Select>
                <Option value="for_each">for_each</Option>
                <Option value="for">for</Option>
                <Option value="while">while</Option>
              </Select>
            </Form.Item>
            <Form.Item label="Array (for_each)" name="array">
              <Input placeholder="items" />
            </Form.Item>
            <Form.Item
              label="Code"
              name="code"
              rules={[{ required: true, message: 'Please enter code' }]}
            >
              <TextArea rows={10} placeholder="result = item" style={{ fontFamily: 'monospace' }} />
            </Form.Item>
            <Form.Item label="Iterations (for)" name="iterations">
              <InputNumber min={1} max={100000} style={{ width: '100%' }} />
            </Form.Item>
          </>
        );

      case 'tool':
        return (
          <>
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
              rules={[{ required: true, message: 'Please enter schema name' }]}
            >
              <Input placeholder="MySchema" />
            </Form.Item>
            <Form.Item label="Mode" name="mode">
              <Select>
                <Option value="object">Object</Option>
                <Option value="array">Array</Option>
              </Select>
            </Form.Item>
            <Form.Item
              label="Schema"
              name="schema"
              rules={[{ required: true, message: 'Please enter schema' }]}
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
