/**
 * Task Classification Page
 *
 * Allows users to:
 * 1. Input task start point and goal
 * 2. Submit for LLM-based classification
 * 3. View classification results with confidence and reasoning
 * 4. See suggested tools for the task
 *
 * GREEN phase (TDD): Implementation
 */

import { useState } from 'react';
import {
  Form,
  Button,
  Input,
  Card,
  Space,
  Result,
  Spin,
  Tag,
  Progress,
  Alert,
  Row,
  Col,
} from 'antd';
import { CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { classifyTask } from '../api/classificationApi';
import type { ClassificationResult, TaskType } from '@/types/workflow';
import styles from '../styles/classification.module.css';

const taskTypeColors: Record<TaskType, string> = {
  data_analysis: 'blue',
  content_creation: 'green',
  research: 'purple',
  problem_solving: 'orange',
  automation: 'cyan',
  unknown: 'default',
};

const taskTypeLabels: Record<TaskType, string> = {
  data_analysis: 'Data Analysis',
  content_creation: 'Content Creation',
  research: 'Research',
  problem_solving: 'Problem Solving',
  automation: 'Automation',
  unknown: 'Unknown',
};

export default function TaskClassificationPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClassificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleClassify = async (values: { start: string; goal: string }) => {
    try {
      setLoading(true);
      setError(null);

      const response = await classifyTask({
        start: values.start,
        goal: values.goal,
      });

      setResult(response.data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Classification failed';
      setError(errorMessage);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    form.resetFields();
    setResult(null);
    setError(null);
  };

  return (
    <div className={styles.container}>
      <Row gutter={[24, 24]}>
        {/* Input Form */}
        <Col xs={24} lg={12}>
          <Card
            title="Task Classification"
            bordered={false}
            className={styles.card}
          >
            <Form
              form={form}
              layout="vertical"
              onFinish={handleClassify}
              autoComplete="off"
            >
              <Form.Item
                label="Task Start Point"
                name="start"
                rules={[
                  {
                    required: true,
                    message: 'Please describe the current state or starting point',
                  },
                  {
                    min: 5,
                    message: 'Please provide more details (at least 5 characters)',
                  },
                ]}
              >
                <Input.TextArea
                  placeholder="e.g., I have a CSV file with sales data from the past year"
                  rows={3}
                />
              </Form.Item>

              <Form.Item
                label="Task Goal"
                name="goal"
                rules={[
                  {
                    required: true,
                    message: 'Please describe the goal or desired outcome',
                  },
                  {
                    min: 5,
                    message: 'Please provide more details (at least 5 characters)',
                  },
                ]}
              >
                <Input.TextArea
                  placeholder="e.g., Analyze sales trends and generate a monthly report with visualizations"
                  rows={3}
                />
              </Form.Item>

              <Space>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  disabled={loading}
                  size="large"
                >
                  {loading ? 'Classifying...' : 'Classify Task'}
                </Button>
                <Button onClick={handleClear} disabled={loading}>
                  Clear
                </Button>
              </Space>
            </Form>
          </Card>
        </Col>

        {/* Results */}
        <Col xs={24} lg={12}>
          {error && (
            <Alert
              message="Classification Error"
              description={error}
              type="error"
              showIcon
              closable
              onClose={() => setError(null)}
              style={{ marginBottom: '16px' }}
            />
          )}

          {loading && (
            <Card className={styles.card}>
              <Spin size="large" />
            </Card>
          )}

          {result && !loading && (
            <>
              {/* Task Type */}
              <Card
                title="Classification Result"
                bordered={false}
                style={{ marginBottom: '16px' }}
                className={styles.card}
              >
                <Space direction="vertical" style={{ width: '100%' }} size="large">
                  <div>
                    <label className={styles.label}>Task Type:</label>
                    <div className={styles.value}>
                      <Tag color={taskTypeColors[result.taskType]} style={{ fontSize: '14px' }}>
                        {taskTypeLabels[result.taskType]}
                      </Tag>
                    </div>
                  </div>

                  {/* Confidence */}
                  <div>
                    <label className={styles.label}>Confidence:</label>
                    <div className={styles.value}>
                      <Progress
                        type="circle"
                        percent={Math.round(result.confidence * 100)}
                        width={80}
                      />
                      <span className={styles.progressText}>
                        {(result.confidence * 100).toFixed(2)}%
                      </span>
                    </div>
                  </div>

                  {/* Reasoning */}
                  <div>
                    <label className={styles.label}>Reasoning:</label>
                    <div className={styles.reasoningBox}>
                      {result.reasoning}
                    </div>
                  </div>

                  {/* Suggested Tools */}
                  {result.suggestedTools && result.suggestedTools.length > 0 && (
                    <div>
                      <label className={styles.label}>Suggested Tools:</label>
                      <div className={styles.value}>
                        <Space wrap>
                          {result.suggestedTools.map((tool) => (
                            <Tag key={tool} color="cyan">
                              {tool}
                            </Tag>
                          ))}
                        </Space>
                      </div>
                    </div>
                  )}
                </Space>
              </Card>

              {/* Success Message */}
              <Result
                icon={<CheckCircleOutlined />}
                title="Classification Complete"
                subTitle="The task has been successfully classified. You can now proceed with the appropriate workflow."
              />
            </>
          )}

          {!result && !loading && !error && (
            <Card className={styles.card}>
              <Result
                icon={<ExclamationCircleOutlined />}
                title="Waiting for Input"
                subTitle="Please fill in the form on the left to classify your task"
              />
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
}
