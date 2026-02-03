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
import { Typography, Switch, Space } from 'antd';
import {
  BulbOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  MessageOutlined,
} from '@ant-design/icons';

import { StreamingChat } from '@/shared/components/StreamingChat';
import { StreamingMessageDisplay } from '@/shared/components/StreamingMessageDisplay';
import { PageShell } from '@/shared/components/layout/PageShell';
import { NeoCard } from '@/shared/components/common/NeoCard';
import type { StreamingMessage } from '@/shared/types/streaming';
import styles from '../styles/demo.module.css';

const { Text, Paragraph } = Typography;

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
  const [, setLastResponse] = useState<string>('');

  return (
    <PageShell
      title="Phase 4: Streaming Demo"
      description="Real-time demonstration of AI thought processes, tool usage, and final responses."
      actions={
        <div className={styles.legend}>
          <div className={styles.legendItem}>
            <BulbOutlined className={styles.colorThought} />
            <span>Thinking</span>
          </div>
          <div className={styles.legendItem}>
            <ToolOutlined className={styles.colorTool} />
            <span>Tool Call</span>
          </div>
          <div className={styles.legendItem}>
            <CheckCircleOutlined className={styles.colorResult} />
            <span>Result</span>
          </div>
          <div className={styles.legendItem}>
            <MessageOutlined className={styles.colorFinal} />
            <span>Response</span>
          </div>
        </div>
      }
    >
      <div className={styles.container}>
        {/* Left: Example Messages */}
        <NeoCard
          title="Message Types"
          variant="raised"
          className={styles.examplePane}
          extra={
            <Space>
              <Text type="secondary" style={{ fontSize: '12px' }}>Show Examples</Text>
              <Switch
                checked={showExamples}
                onChange={setShowExamples}
                size="small"
              />
            </Space>
          }
        >
          {showExamples ? (
            <div className={styles.exampleList}>
              <div style={{ padding: '0 16px' }}>
                <Paragraph type="secondary" style={{ marginBottom: '24px' }}>
                  These examples demonstrate how different message types are rendered in the stream.
                </Paragraph>

                {exampleMessages.map((msg, index) => (
                  <div key={msg.message_id} className={styles.exampleItem}>
                    <span className={styles.stepLabel}>Step {index + 1} • {msg.type.toUpperCase()}</span>
                    <StreamingMessageDisplay
                      message={msg}
                      showDetails={true}
                    />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{
              height: '600px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--neo-text-2)'
            }}>
              Examples hidden
            </div>
          )}
        </NeoCard>

        {/* Right: Live Chat */}
        <div className={styles.chatContainer}>
          <StreamingChat
            showWelcome={true}
            showIntermediateSteps={true}
            onFinalResponse={(content) => setLastResponse(content)}
            style={{ height: '100%', border: '1px solid var(--neo-border)', borderRadius: 'var(--radius-md)' }}
          />
        </div>
      </div>

      {/* Tech Specs */}
      <NeoCard title="Technical Implementation" variant="flat" style={{ marginTop: 'var(--spacing-6)' }}>
        <div className={styles.techSpecs}>
          <div className={styles.techSpecColumn}>
            <h5>Backend Architecture</h5>
            <ul className={styles.techSpecList}>
              <li>ConversationFlowEmitter</li>
              <li>StreamMessageFormatter</li>
              <li>SSEEmitterHandler</li>
              <li>/api/conversation/stream</li>
            </ul>
          </div>
          <div className={styles.techSpecColumn}>
            <h5>Frontend Components</h5>
            <ul className={styles.techSpecList}>
              <li>useConversationStream Hook</li>
              <li>StreamingMessageDisplay</li>
              <li>StreamingChat Component</li>
              <li>Strict Type Definitions</li>
            </ul>
          </div>
          <div className={styles.techSpecColumn}>
            <h5>Data Flow</h5>
            <ul className={styles.techSpecList}>
              <li>User Input &rarr; SSE Connection</li>
              <li>Real-time Chunk Streaming</li>
              <li>Differential Rendering</li>
              <li>Auto-scrolling & State Management</li>
            </ul>
          </div>
        </div>
      </NeoCard>
    </PageShell>
  );
};

export default StreamingDemoPage;
