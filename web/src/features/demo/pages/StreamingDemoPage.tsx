/**
 * Phase 4: 流式消息 Demo 页面
 *
 * 展示实时流式消息功能：
 * - thought: 思考过程
 * - tool_call: 工具调用
 * - tool_result: 工具结果
 * - final: 最终响应
 */

import React, { useState } from 'react';
import { Layout, Typography, Card, Row, Col, Divider, Switch, Space, Alert, Button } from 'antd';
import {
  ExperimentOutlined,
  BulbOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  MessageOutlined,
} from '@ant-design/icons';

import { StreamingChat } from '@/shared/components/StreamingChat';
import { StreamingMessageDisplay } from '@/shared/components/StreamingMessageDisplay';
import type { StreamingMessage } from '@/shared/types/streaming';

const { Content } = Layout;
const { Title, Text, Paragraph } = Typography;

// 示例消息
const exampleMessages: StreamingMessage[] = [
  {
    type: 'thought',
    content: '用户想了解天气情况，我需要调用天气查询工具。',
    metadata: {},
    timestamp: new Date().toISOString(),
    sequence: 1,
    is_streaming: false,
    message_id: 'example_1',
  },
  {
    type: 'tool_call',
    content: '',
    metadata: {
      tool: 'weather_query',
      tool_id: 'weather_001',
      arguments: { city: '北京', date: 'today' },
    },
    timestamp: new Date().toISOString(),
    sequence: 2,
    is_streaming: false,
    message_id: 'example_2',
  },
  {
    type: 'tool_result',
    content: '',
    metadata: {
      tool_id: 'weather_001',
      result: { temperature: 25, condition: '晴朗', humidity: '45%' },
      success: true,
    },
    timestamp: new Date().toISOString(),
    sequence: 3,
    is_streaming: false,
    message_id: 'example_3',
  },
  {
    type: 'final',
    content: '北京今天天气晴朗，气温 25°C，湿度 45%，非常适合户外活动。',
    metadata: { is_final: true },
    timestamp: new Date().toISOString(),
    sequence: 4,
    is_streaming: false,
    message_id: 'example_4',
  },
];

export const StreamingDemoPage: React.FC = () => {
  const [showExamples, setShowExamples] = useState(true);
  const [lastResponse, setLastResponse] = useState<string>('');

  return (
    <Layout style={{ minHeight: '100vh', backgroundColor: '#0a0a0a' }}>
      <Content style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
        {/* 标题 */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <Title level={2} style={{ color: '#fafafa', marginBottom: '8px' }}>
            <ExperimentOutlined style={{ marginRight: '12px', color: '#8b5cf6' }} />
            Phase 4: 流式消息展示 Demo
          </Title>
          <Paragraph style={{ color: '#8c8c8c', fontSize: '16px' }}>
            实时展示 AI 思考过程、工具调用和最终响应
          </Paragraph>
        </div>

        {/* 功能介绍 */}
        <Alert
          type="info"
          showIcon
          message="消息类型说明"
          description={
            <Row gutter={[16, 8]} style={{ marginTop: '8px' }}>
              <Col span={6}>
                <Space>
                  <BulbOutlined style={{ color: '#8b5cf6' }} />
                  <Text style={{ color: '#d1d5db' }}>💭 thought: 思考过程</Text>
                </Space>
              </Col>
              <Col span={6}>
                <Space>
                  <ToolOutlined style={{ color: '#3b82f6' }} />
                  <Text style={{ color: '#d1d5db' }}>🔧 tool_call: 工具调用</Text>
                </Space>
              </Col>
              <Col span={6}>
                <Space>
                  <CheckCircleOutlined style={{ color: '#22c55e' }} />
                  <Text style={{ color: '#d1d5db' }}>📋 tool_result: 工具结果</Text>
                </Space>
              </Col>
              <Col span={6}>
                <Space>
                  <MessageOutlined style={{ color: '#10b981' }} />
                  <Text style={{ color: '#d1d5db' }}>✅ final: 最终响应</Text>
                </Space>
              </Col>
            </Row>
          }
          style={{ marginBottom: '24px', backgroundColor: '#1a1a2e', borderColor: '#3b3b5a' }}
        />

        <Row gutter={24}>
          {/* 左侧：示例消息展示 */}
          <Col span={10}>
            <Card
              title={
                <Space>
                  <span style={{ color: '#fafafa' }}>消息类型示例</span>
                  <Switch
                    checked={showExamples}
                    onChange={setShowExamples}
                    size="small"
                  />
                </Space>
              }
              style={{
                backgroundColor: '#141414',
                borderColor: '#262626',
                height: '600px',
                overflow: 'auto',
              }}
              styles={{
                header: { backgroundColor: '#1a1a1a', borderBottom: '1px solid #262626' },
                body: { backgroundColor: '#141414', padding: '16px' },
              }}
            >
              {showExamples && (
                <div>
                  <Paragraph style={{ color: '#8c8c8c', marginBottom: '16px' }}>
                    以下是不同类型消息的展示效果：
                  </Paragraph>

                  {exampleMessages.map((msg, index) => (
                    <div key={msg.message_id} style={{ marginBottom: '16px' }}>
                      <Text
                        type="secondary"
                        style={{
                          fontSize: '11px',
                          display: 'block',
                          marginBottom: '4px',
                        }}
                      >
                        Step {index + 1}: {msg.type}
                      </Text>
                      <StreamingMessageDisplay
                        message={msg}
                        showDetails={true}
                      />
                    </div>
                  ))}

                  <Divider style={{ borderColor: '#262626' }} />

                  <Paragraph style={{ color: '#8c8c8c', fontSize: '12px' }}>
                    💡 提示：在右侧聊天框发送消息，将看到实时的流式响应。
                  </Paragraph>
                </div>
              )}
            </Card>
          </Col>

          {/* 右侧：实时聊天 */}
          <Col span={14}>
            <StreamingChat
              showWelcome={true}
              showIntermediateSteps={true}
              onFinalResponse={(content) => setLastResponse(content)}
              style={{ height: '600px' }}
            />
          </Col>
        </Row>

        {/* 最后响应显示 */}
        {lastResponse && (
          <Card
            title={<Text style={{ color: '#fafafa' }}>最后收到的响应</Text>}
            style={{
              marginTop: '24px',
              backgroundColor: '#141414',
              borderColor: '#262626',
            }}
            styles={{
              header: { backgroundColor: '#1a1a1a', borderBottom: '1px solid #262626' },
              body: { backgroundColor: '#141414' },
            }}
          >
            <Paragraph style={{ color: '#d1d5db', whiteSpace: 'pre-wrap' }}>
              {lastResponse}
            </Paragraph>
          </Card>
        )}

        {/* 技术说明 */}
        <Card
          title={<Text style={{ color: '#fafafa' }}>技术实现</Text>}
          style={{
            marginTop: '24px',
            backgroundColor: '#141414',
            borderColor: '#262626',
          }}
          styles={{
            header: { backgroundColor: '#1a1a1a', borderBottom: '1px solid #262626' },
            body: { backgroundColor: '#141414' },
          }}
        >
          <Row gutter={24}>
            <Col span={8}>
              <Title level={5} style={{ color: '#8b5cf6' }}>后端</Title>
              <ul style={{ color: '#8c8c8c', paddingLeft: '20px' }}>
                <li>ConversationFlowEmitter: 消息队列管理</li>
                <li>StreamMessageFormatter: 格式化为前端格式</li>
                <li>SSEEmitterHandler: SSE 流式传输</li>
                <li>/api/conversation/stream: 流式端点</li>
              </ul>
            </Col>
            <Col span={8}>
              <Title level={5} style={{ color: '#3b82f6' }}>前端</Title>
              <ul style={{ color: '#8c8c8c', paddingLeft: '20px' }}>
                <li>useConversationStream: 流式数据 Hook</li>
                <li>StreamingMessageDisplay: 消息展示组件</li>
                <li>StreamingChat: 集成聊天组件</li>
                <li>类型定义: streaming.ts</li>
              </ul>
            </Col>
            <Col span={8}>
              <Title level={5} style={{ color: '#22c55e' }}>数据流</Title>
              <ul style={{ color: '#8c8c8c', paddingLeft: '20px' }}>
                <li>用户发送消息</li>
                <li>SSE 连接建立</li>
                <li>实时接收 thought/tool/final</li>
                <li>组件差异化渲染</li>
              </ul>
            </Col>
          </Row>
        </Card>
      </Content>
    </Layout>
  );
};

export default StreamingDemoPage;
