/**
 * Scheduled Workflows Page
 *
 * Manages scheduled workflow operations:
 * 1. List all scheduled workflows with status
 * 2. Create new scheduled workflows
 * 3. Edit cron expressions and retries
 * 4. Trigger manual execution
 * 5. Pause/Resume workflows
 * 6. Delete workflows
 * 7. View execution history
 *
 * GREEN phase (TDD): Implementation
 */

import { useState } from 'react';
import {
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Tag,
  Spin,
  Alert,
  Row,
  Col,
  Card,
  message,
} from 'antd';
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as scheduledWorkflowsApi from '../api/scheduledWorkflowsApi';
import * as workflowsApi from '../../workflows/api/workflowsApi';
import { ScheduledWorkflow } from '../../../types/workflow';
import './ScheduledWorkflowsPage.css';

const statusColors: Record<string, string> = {
  active: 'green',
  disabled: 'red',
  paused: 'orange',
};

export default function ScheduledWorkflowsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedWorkflow, setSelectedWorkflow] = useState<ScheduledWorkflow | null>(null);

  // Load scheduled workflows
  const {
    data: scheduledWorkflows = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['scheduledWorkflows'],
    queryFn: async () => {
      const response = await scheduledWorkflowsApi.listScheduledWorkflows();
      return response.data;
    },
  });

  // Load available workflows for creation
  const { data: availableWorkflows = [] } = useQuery({
    queryKey: ['workflows'],
    queryFn: async () => {
      const response = await workflowsApi.listWorkflows();
      return response.data;
    },
  });

  // Create scheduled workflow mutation
  const createMutation = useMutation({
    mutationFn: (data: {
      workflowId: string;
      cronExpression: string;
      maxRetries: number;
    }) =>
      scheduledWorkflowsApi.createScheduledWorkflow(data.workflowId, {
        cronExpression: data.cronExpression,
        maxRetries: data.maxRetries,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      message.success('Scheduled workflow created successfully');
      setIsModalOpen(false);
      form.resetFields();
    },
    onError: () => {
      message.error('Failed to create scheduled workflow');
    },
  });

  // Trigger execution mutation
  const triggerMutation = useMutation({
    mutationFn: (id: string) => scheduledWorkflowsApi.triggerExecution(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      message.success('Execution triggered successfully');
    },
    onError: () => {
      message.error('Failed to trigger execution');
    },
  });

  // Pause workflow mutation
  const pauseMutation = useMutation({
    mutationFn: (id: string) => scheduledWorkflowsApi.pauseScheduledWorkflow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      message.success('Workflow paused successfully');
    },
    onError: () => {
      message.error('Failed to pause workflow');
    },
  });

  // Resume workflow mutation
  const resumeMutation = useMutation({
    mutationFn: (id: string) => scheduledWorkflowsApi.resumeScheduledWorkflow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      message.success('Workflow resumed successfully');
    },
    onError: () => {
      message.error('Failed to resume workflow');
    },
  });

  // Delete workflow mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => scheduledWorkflowsApi.deleteScheduledWorkflow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      message.success('Workflow deleted successfully');
    },
    onError: () => {
      message.error('Failed to delete workflow');
    },
  });

  const handleCreateOpen = () => {
    setSelectedWorkflow(null);
    form.resetFields();
    setIsModalOpen(true);
  };

  const handleCreateSubmit = (values: any) => {
    createMutation.mutate({
      workflowId: values.workflowId,
      cronExpression: values.cronExpression,
      maxRetries: values.maxRetries,
    });
  };

  const handleDeleteConfirm = (record: ScheduledWorkflow) => {
    Modal.confirm({
      title: 'Delete Scheduled Workflow',
      content: `Are you sure you want to delete this scheduled workflow?`,
      okText: 'Delete',
      okType: 'danger',
      onOk: () => {
        deleteMutation.mutate(record.id);
      },
    });
  };

  const columns = [
    {
      title: 'Workflow ID',
      dataIndex: 'workflowId',
      key: 'workflowId',
      width: '15%',
    },
    {
      title: 'Cron Expression',
      dataIndex: 'cronExpression',
      key: 'cronExpression',
      width: '15%',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: '10%',
      render: (status: string) => (
        <Tag color={statusColors[status]}>{status.toUpperCase()}</Tag>
      ),
    },
    {
      title: 'Max Retries',
      dataIndex: 'maxRetries',
      key: 'maxRetries',
      width: '10%',
    },
    {
      title: 'Failures',
      dataIndex: 'consecutiveFailures',
      key: 'consecutiveFailures',
      width: '10%',
    },
    {
      title: 'Last Execution',
      dataIndex: 'lastExecutionStatus',
      key: 'lastExecutionStatus',
      width: '15%',
      render: (status: string) =>
        status ? (
          <Tag color={status === 'success' ? 'green' : 'red'}>
            {status.toUpperCase()}
          </Tag>
        ) : (
          '-'
        ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: '25%',
      render: (text: any, record: ScheduledWorkflow) => (
        <Space size="small" wrap>
          <Button
            type="primary"
            size="small"
            icon={<PlayCircleOutlined />}
            loading={triggerMutation.isPending && triggerMutation.variables === record.id}
            onClick={() => triggerMutation.mutate(record.id)}
          >
            Trigger
          </Button>
          {record.status === 'active' ? (
            <Button
              type="default"
              size="small"
              icon={<PauseCircleOutlined />}
              loading={pauseMutation.isPending && pauseMutation.variables === record.id}
              onClick={() => pauseMutation.mutate(record.id)}
            >
              Pause
            </Button>
          ) : (
            <Button
              type="default"
              size="small"
              icon={<PlayCircleOutlined />}
              loading={resumeMutation.isPending && resumeMutation.variables === record.id}
              onClick={() => resumeMutation.mutate(record.id)}
            >
              Resume
            </Button>
          )}
          <Button
            type="primary"
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteConfirm(record)}
          >
            Delete
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div className="scheduled-workflows-page">
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card
            title="Scheduled Workflows"
            extra={
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleCreateOpen}
              >
                Create Scheduled Workflow
              </Button>
            }
          >
            {error && (
              <Alert
                message="Error loading scheduled workflows"
                type="error"
                showIcon
                style={{ marginBottom: '16px' }}
              />
            )}

            {isLoading ? (
              <Spin size="large" />
            ) : (
              <Table
                columns={columns}
                dataSource={scheduledWorkflows}
                rowKey="id"
                pagination={{ pageSize: 10 }}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* Create Modal */}
      <Modal
        title="Create Scheduled Workflow"
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setIsModalOpen(false)}>
            Cancel
          </Button>,
          <Button
            key="create"
            type="primary"
            loading={createMutation.isPending}
            onClick={() => form.submit()}
          >
            Create
          </Button>,
        ]}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateSubmit}
          autoComplete="off"
        >
          <Form.Item
            label="Workflow"
            name="workflowId"
            rules={[
              {
                required: true,
                message: 'Please select a workflow',
              },
            ]}
          >
            <Select placeholder="Select a workflow to schedule">
              {availableWorkflows.map((wf: any) => (
                <Select.Option key={wf.id} value={wf.id}>
                  {wf.name || wf.id}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="Cron Expression"
            name="cronExpression"
            rules={[
              {
                required: true,
                message: 'Please enter a cron expression',
              },
              {
                pattern: /^(\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*\/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) (\*|([0-9]|1[0-9]|2[0-3])|\*\/([0-9]|1[0-9]|2[0-3])) (\*|([1-9]|1[0-9]|2[0-9]|3[0-1])|\*\/([1-9]|1[0-9]|2[0-9]|3[0-1])) (\*|([1-9]|1[0-2])|\*\/([1-9]|1[0-2])) (\*|([0-6])|\*\/([0-6]))$/,
                message: 'Please enter a valid cron expression (5 fields)',
              },
            ]}
          >
            <Input placeholder="e.g., */5 * * * * (every 5 minutes)" />
          </Form.Item>

          <Form.Item
            label="Max Retries"
            name="maxRetries"
            rules={[
              {
                required: true,
                message: 'Please enter max retries',
              },
            ]}
            initialValue={3}
          >
            <InputNumber min={0} max={10} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
