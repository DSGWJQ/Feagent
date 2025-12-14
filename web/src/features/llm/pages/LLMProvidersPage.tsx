import { useState } from 'react';
import {
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  message,
  Alert,
  Switch,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { PageShell } from '@/shared/components/layout/PageShell';
import { NeoCard } from '@/shared/components/common/NeoCard';
import styles from '../styles/llm.module.css';

const providerTypes = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Qwen', value: 'qwen' },
  { label: 'Claude', value: 'claude' },
  { label: 'Ollama (Local)', value: 'ollama' },
  { label: 'Google Gemini', value: 'gemini' },
];

export default function LLMProvidersPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<any>(null);

  const mockProviders = [
    {
      id: 'provider_1',
      name: 'OpenAI Official',
      type: 'openai',
      baseUrl: 'https://api.openai.com/v1',
      model: 'gpt-4o',
      enabled: true,
      apiKeyMasked: 'sk-***...***',
    },
    {
      id: 'provider_2',
      name: 'DeepSeek China',
      type: 'deepseek',
      baseUrl: 'https://api.deepseek.com',
      model: 'deepseek-chat',
      enabled: true,
      apiKeyMasked: 'sk-***...***',
    },
    {
      id: 'provider_3',
      name: 'Local Ollama',
      type: 'ollama',
      baseUrl: 'http://localhost:11434',
      model: 'mistral',
      enabled: false,
      apiKeyMasked: 'N/A',
    },
    {
      id: 'provider_4',
      name: 'Google Gemini',
      type: 'gemini',
      baseUrl: 'https://generativelanguage.googleapis.com/v1beta',
      model: 'gemini-1.5-pro',
      enabled: true,
      apiKeyMasked: 'AIz***...***',
    }
  ];

  const { data: providers = mockProviders, isLoading, error } = useQuery({
    queryKey: ['llmProviders'],
    queryFn: async () => {
      // Return mock data for now, would be API call
      await new Promise((resolve) => setTimeout(resolve, 500));
      return mockProviders;
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => {
      return new Promise((resolve) => {
        setTimeout(() => {
          resolve({ data: { ...data, id: `provider_${Date.now()}` } });
        }, 500);
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llmProviders'] });
      message.success('Provider registered successfully');
      setIsModalOpen(false);
      form.resetFields();
    },
    onError: () => {
      message.error('Failed to register provider');
    },
  });

  const updateMutation = useMutation({
    /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
    mutationFn: (data: any) => {
      return new Promise((resolve) => {
        setTimeout(() => resolve(null), 500);
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llmProviders'] });
      message.success('Provider updated successfully');
      setIsModalOpen(false); // Should close modal on update too
      form.resetFields();
    },
    onError: () => {
      message.error('Failed to update provider');
    },
  });

  const deleteMutation = useMutation({
    /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
    mutationFn: (id: string) => {
      return new Promise((resolve) => {
        setTimeout(() => resolve(null), 500);
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llmProviders'] });
      message.success('Provider deleted successfully');
    },
    onError: () => {
      message.error('Failed to delete provider');
    },
  });

  const handleCreateOpen = () => {
    setEditingProvider(null);
    form.resetFields();
    setIsModalOpen(true);
  };

  const handleCreateSubmit = (values: any) => {
    if (editingProvider) {
      updateMutation.mutate({ ...values, id: editingProvider.id });
    } else {
      createMutation.mutate(values);
    }
  };

  const handleDeleteConfirm = (providerId: string) => {
    Modal.confirm({
      title: 'Delete Provider',
      content: 'Are you sure you want to delete this LLM provider?',
      okText: 'Delete',
      okType: 'danger',
      onOk: () => {
        deleteMutation.mutate(providerId);
      },
    });
  };

  const columns = [
    {
      title: 'Provider Name',
      dataIndex: 'name',
      key: 'name',
      width: '15%',
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: '12%',
      render: (type: string) => {
        const provider = providerTypes.find((p) => p.value === type);
        let color = 'cyan';
        if (type === 'openai') color = 'green';
        if (type === 'claude') color = 'purple';
        if (type === 'gemini') color = 'blue';

        return <Tag color={color}>{provider?.label}</Tag>;
      },
    },
    {
      title: 'Base URL',
      dataIndex: 'baseUrl',
      key: 'baseUrl',
      width: '20%',
      render: (url: string) => (
        <span className={styles.urlText}>{url}</span>
      ),
    },
    {
      title: 'Model',
      dataIndex: 'model',
      key: 'model',
      width: '15%',
    },
    {
      title: 'API Key',
      dataIndex: 'apiKeyMasked',
      key: 'apiKeyMasked',
      width: '12%',
      render: (masked: string) => (
        <span className={styles.maskText}>{masked}</span>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'enabled',
      key: 'enabled',
      width: '10%',
      render: (enabled: boolean) =>
        enabled ? (
          <Tag icon={<CheckCircleOutlined />} color="success">
            Enabled
          </Tag>
        ) : (
          <Tag icon={<CloseCircleOutlined />} color="default">
            Disabled
          </Tag>
        ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: '16%',
      render: (_: any, record: any) => (
        <Space size="small" wrap>
          <Button
            type="primary"
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingProvider(record);
              form.setFieldsValue(record);
              setIsModalOpen(true);
            }}
          >
            Edit
          </Button>
          <Button
            type="primary"
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteConfirm(record.id)}
          >
            Delete
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <PageShell
      title="LLM Providers"
      description="Manage connections to Large Language Model providers (OpenAI, DeepSeek, Local Ollama, etc)."
      actions={
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreateOpen}
        >
          Register Provider
        </Button>
      }
    >
      <div className={styles.container}>
        <NeoCard
          title="Active Providers"
          variant="standard"
          className={styles.card}
        >
          {error && (
            <Alert
              message="Error loading providers"
              type="error"
              showIcon
              style={{ marginBottom: '16px' }}
            />
          )}

          <Table
            className={`${styles.neoTable}`}
            columns={columns}
            dataSource={providers}
            rowKey="id"
            loading={isLoading}
            pagination={{ pageSize: 10 }}
          />
        </NeoCard>
      </div>

      <Modal
        title={editingProvider ? 'Edit LLM Provider' : 'Register New LLM Provider'}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setIsModalOpen(false)}>
            Cancel
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={createMutation.isPending || updateMutation.isPending}
            onClick={() => form.submit()}
          >
            {editingProvider ? 'Update' : 'Register'}
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
            label="Provider Name"
            name="name"
            rules={[
              { required: true, message: 'Please enter provider name' },
            ]}
          >
            <Input placeholder="e.g., OpenAI Official" />
          </Form.Item>

          <Form.Item
            label="Provider Type"
            name="type"
            rules={[
              { required: true, message: 'Please select provider type' },
            ]}
          >
            <Select placeholder="Select provider type">
              {providerTypes.map((type) => (
                <Select.Option key={type.value} value={type.value}>
                  {type.label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="Base URL"
            name="baseUrl"
            rules={[
              { required: true, message: 'Please enter base URL' },
              {
                pattern: /^https?:\/\/.+/,
                message: 'Please enter a valid URL',
              },
            ]}
          >
            <Input placeholder="https://api.example.com/v1" />
          </Form.Item>

          <Form.Item
            label="Model Name"
            name="model"
            rules={[{ required: true, message: 'Please enter model name' }]}
          >
            <Input placeholder="e.g., gpt-4o, deepseek-chat" />
          </Form.Item>

          <Form.Item
            label="API Key"
            name="apiKey"
            rules={[{ required: true, message: 'Please enter API key' }]}
          >
            <Input.Password placeholder="Enter your API key" />
          </Form.Item>

          <Form.Item
            label="Enabled"
            name="enabled"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}
