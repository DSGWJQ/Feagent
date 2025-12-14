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
  ConfigProvider,
  theme,
} from 'antd';
import type { Node } from '@xyflow/react';

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

  useEffect(() => {
    if (node) {
      form.setFieldsValue(node.data);
    }
  }, [node, form]);

  const handleSave = () => {
    const values = form.getFieldsValue();
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

      case 'tool':
        return (
          <>
            <Form.Item
              label="Tool Name"
              name="name"
              rules={[{ required: true, message: 'Please enter tool name' }]}
            >
              <Input placeholder="myTool" />
            </Form.Item>
            <Form.Item
              label="Description"
              name="description"
              rules={[{ required: true, message: 'Please enter description' }]}
            >
              <TextArea rows={2} placeholder="Tool description" />
            </Form.Item>
            <Form.Item
              label="Code"
              name="code"
              rules={[{ required: true, message: 'Please enter code' }]}
            >
              <TextArea
                rows={10}
                placeholder="async function execute(args) {&#10;  return result;&#10;}"
                style={{ fontFamily: 'monospace' }}
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
