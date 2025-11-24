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
  Card,
  message,
  Alert,
  Row,
  Col,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  CheckOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import './ToolsLibraryPage.css';

const toolCategories = [
  { label: 'Database', value: 'database' },
  { label: 'API', value: 'api' },
  { label: 'File Processing', value: 'file_processing' },
  { label: 'Visualization', value: 'visualization' },
  { label: 'Text Processing', value: 'text_processing' },
  { label: 'Data Analysis', value: 'data_analysis' },
];

const toolStatuses = [
  { label: 'Draft', value: 'draft', color: 'default' },
  { label: 'Published', value: 'published', color: 'green' },
  { label: 'Deprecated', value: 'deprecated', color: 'red' },
];

export default function ToolsLibraryPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTool, setEditingTool] = useState(null);

  const mockTools = [
    {
      id: 'tool_1',
      name: 'PostgreSQL Database',
      description: 'Connect and query PostgreSQL databases',
      category: 'database',
      version: '1.0.0',
      status: 'published',
    },
    {
      id: 'tool_2',
      name: 'REST API Client',
      description: 'Make HTTP requests to REST APIs',
      category: 'api',
      version: '2.1.0',
      status: 'published',
    },
    {
      id: 'tool_3',
      name: 'CSV Parser',
      description: 'Parse and process CSV files',
      category: 'file_processing',
      version: '1.5.0',
      status: 'published',
    },
  ];

  const { data: tools = mockTools, isLoading, error } = useQuery({
    queryKey: ['tools'],
    queryFn: async () => {
      await new Promise((resolve) => setTimeout(resolve, 500));
      return mockTools;
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => {
      return new Promise((resolve) => {
        setTimeout(() => {
          resolve({ data: { ...data, id: `tool_${Date.now()}` } });
        }, 500);
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] });
      message.success('Tool created successfully');
      setIsModalOpen(false);
      form.resetFields();
    },
    onError: () => {
      message.error('Failed to create tool');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => {
      return new Promise((resolve) => {
        setTimeout(() => resolve(null), 500);
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] });
      message.success('Tool deleted successfully');
    },
    onError: () => {
      message.error('Failed to delete tool');
    },
  });

  const publishMutation = useMutation({
    mutationFn: (id: string) => {
      return new Promise((resolve) => {
        setTimeout(() => resolve(null), 500);
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] });
      message.success('Tool published successfully');
    },
    onError: () => {
      message.error('Failed to publish tool');
    },
  });

  const handleCreateOpen = () => {
    setEditingTool(null);
    form.resetFields();
    setIsModalOpen(true);
  };

  const handleCreateSubmit = (values: any) => {
    createMutation.mutate(values);
  };

  const handleDeleteConfirm = (toolId: string) => {
    Modal.confirm({
      title: 'Delete Tool',
      content: 'Are you sure you want to delete this tool?',
      okText: 'Delete',
      okType: 'danger',
      onOk: () => {
        deleteMutation.mutate(toolId);
      },
    });
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: '15%',
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      width: '25%',
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
      width: '12%',
      render: (category: string) => (
        <Tag color="blue">{category.replace(/_/g, ' ').toUpperCase()}</Tag>
      ),
    },
    {
      title: 'Version',
      dataIndex: 'version',
      key: 'version',
      width: '10%',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: '12%',
      render: (status: string) => {
        const statusConfig = toolStatuses.find((s) => s.value === status);
        return (
          <Tag color={statusConfig?.color}>{statusConfig?.label}</Tag>
        );
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: '26%',
      render: (text: any, record: any) => (
        <Space size="small" wrap>
          <Button
            type="primary"
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingTool(record);
              form.setFieldsValue(record);
              setIsModalOpen(true);
            }}
          >
            Edit
          </Button>
          {record.status === 'draft' && (
            <Button
              type="default"
              size="small"
              icon={<CheckOutlined />}
              loading={
                publishMutation.isPending &&
                publishMutation.variables === record.id
              }
              onClick={() => publishMutation.mutate(record.id)}
            >
              Publish
            </Button>
          )}
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
    <div className="tools-library-page">
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card
            title="Tools Library"
            extra={
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleCreateOpen}
              >
                Add Tool
              </Button>
            }
          >
            {error && (
              <Alert
                message="Error loading tools"
                type="error"
                showIcon
                style={{ marginBottom: '16px' }}
              />
            )}

            <Table
              columns={columns}
              dataSource={tools}
              rowKey="id"
              loading={isLoading}
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </Col>
      </Row>

      <Modal
        title={editingTool ? 'Edit Tool' : 'Create New Tool'}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setIsModalOpen(false)}>
            Cancel
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={createMutation.isPending}
            onClick={() => form.submit()}
          >
            {editingTool ? 'Update' : 'Create'}
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
            label="Tool Name"
            name="name"
            rules={[
              { required: true, message: 'Please enter tool name' },
              { min: 3, message: 'Name must be at least 3 characters' },
            ]}
          >
            <Input placeholder="e.g., PostgreSQL Database" />
          </Form.Item>

          <Form.Item
            label="Description"
            name="description"
            rules={[
              { required: true, message: 'Please enter description' },
            ]}
          >
            <Input.TextArea
              placeholder="Describe what this tool does"
              rows={3}
            />
          </Form.Item>

          <Form.Item
            label="Category"
            name="category"
            rules={[
              { required: true, message: 'Please select a category' },
            ]}
          >
            <Select placeholder="Select tool category">
              {toolCategories.map((cat) => (
                <Select.Option key={cat.value} value={cat.value}>
                  {cat.label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="Version"
            name="version"
            rules={[{ required: true, message: 'Please enter version' }]}
            initialValue="1.0.0"
          >
            <Input placeholder="e.g., 1.0.0" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
