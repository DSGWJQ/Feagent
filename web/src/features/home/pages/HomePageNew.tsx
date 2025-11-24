/**
 * Home Page / Dashboard
 *
 * Landing page with:
 * 1. Quick statistics (total workflows, scheduled tasks, recent executions)
 * 2. Quick action buttons for common tasks
 * 3. Recent activity feed
 * 4. Quick links to all major pages
 *
 * GREEN phase (TDD): Implementation
 */

import { Card, Row, Col, Button, Space, Statistic, List, Tag, Empty } from 'antd';
import {
  PlusOutlined,
  FileTextOutlined,
  ScheduleOutlined,
  DashboardOutlined,
  FormatPainterOutlined,
  AppstoreOutlined,
  ApiOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import * as workflowsApi from '../../workflows/api/workflowsApi';
import * as scheduledWorkflowsApi from '../../scheduler/api/scheduledWorkflowsApi';
import * as schedulerApi from '../../scheduler/api/schedulerApi';
import '../HomePage.css';

const QuickActionCard = ({
  icon,
  title,
  description,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}) => (
  <Card
    hoverable
    style={{
      textAlign: 'center',
      cursor: 'pointer',
      borderRadius: '8px',
      transition: 'all 0.3s',
    }}
    onClick={onClick}
  >
    <div style={{ fontSize: '24px', marginBottom: '8px' }}>{icon}</div>
    <h3 style={{ margin: '8px 0' }}>{title}</h3>
    <p style={{ color: '#666', margin: 0, fontSize: '12px' }}>{description}</p>
  </Card>
);

export default function HomePageNew() {
  const navigate = useNavigate();

  // Load workflow statistics
  const { data: workflows = [] } = useQuery({
    queryKey: ['workflows'],
    queryFn: async () => {
      const response = await workflowsApi.listWorkflows();
      return response.data || [];
    },
  });

  // Load scheduled workflows
  const { data: scheduledWorkflows = [] } = useQuery({
    queryKey: ['scheduledWorkflows'],
    queryFn: async () => {
      const response = await scheduledWorkflowsApi.listScheduledWorkflows();
      return response.data || [];
    },
  });

  // Load scheduler status
  const { data: schedulerStatus } = useQuery({
    queryKey: ['schedulerStatus'],
    queryFn: async () => {
      const response = await schedulerApi.getSchedulerStatus();
      return response.data;
    },
  });

  const activeScheduledWorkflows = scheduledWorkflows.filter(
    (sw) => sw.status === 'active'
  ).length;

  const recentExecutions = scheduledWorkflows
    .filter((sw) => sw.lastExecutionStatus)
    .slice(0, 5)
    .map((sw) => ({
      id: sw.id,
      workflow: sw.workflowId,
      status: sw.lastExecutionStatus,
      time: sw.lastExecutionAt,
    }));

  return (
    <div className="home-page-dashboard">
      {/* Header Section */}
      <Row gutter={[16, 16]} style={{ marginBottom: '32px' }}>
        <Col span={24}>
          <h1 style={{ margin: 0 }}>Feagent Dashboard</h1>
          <p style={{ color: '#666', marginTop: '8px' }}>
            Enterprise Workflow Orchestration & Scheduling Platform
          </p>
        </Col>
      </Row>

      {/* Key Statistics */}
      <Row gutter={[16, 16]} style={{ marginBottom: '32px' }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Workflows"
              value={workflows.length}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Scheduled Workflows"
              value={scheduledWorkflows.length}
              prefix={<ScheduleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Active Schedules"
              value={activeScheduledWorkflows}
              prefix={<DashboardOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Jobs in Scheduler"
              value={schedulerStatus?.totalJobsInScheduler || 0}
              prefix={<ScheduleOutlined />}
              valueStyle={{ color: '#eb2f96' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Quick Actions */}
      <Row gutter={[16, 16]} style={{ marginBottom: '32px' }}>
        <Col span={24}>
          <h2 style={{ marginBottom: '16px' }}>Quick Actions</h2>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <QuickActionCard
            icon={<FileTextOutlined style={{ color: '#1890ff' }} />}
            title="Create Workflow"
            description="Design a new workflow"
            onClick={() => navigate('/editor')}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <QuickActionCard
            icon={<ScheduleOutlined style={{ color: '#52c41a' }} />}
            title="Schedule Task"
            description="Schedule a workflow"
            onClick={() => navigate('/scheduled')}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <QuickActionCard
            icon={<FormatPainterOutlined style={{ color: '#faad14' }} />}
            title="Classify Task"
            description="AI-powered task analysis"
            onClick={() => navigate('/classification')}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <QuickActionCard
            icon={<DashboardOutlined style={{ color: '#eb2f96' }} />}
            title="Monitor"
            description="View scheduler status"
            onClick={() => navigate('/monitor')}
          />
        </Col>
      </Row>

      {/* Recent Activity */}
      <Row gutter={[16, 16]} style={{ marginBottom: '32px' }}>
        <Col span={24}>
          <Card title="Recent Executions" bordered={false}>
            {recentExecutions.length > 0 ? (
              <List
                dataSource={recentExecutions}
                renderItem={(item) => (
                  <List.Item>
                    <List.Item.Meta
                      title={item.workflow}
                      description={
                        <>
                          <span>
                            {new Date(item.time || '').toLocaleString()}
                          </span>
                          <Tag
                            color={item.status === 'success' ? 'green' : 'red'}
                            style={{ marginLeft: '8px' }}
                          >
                            {item.status?.toUpperCase()}
                          </Tag>
                        </>
                      }
                    />
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="No recent executions" />
            )}
          </Card>
        </Col>
      </Row>

      {/* Navigation Cards */}
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <h2 style={{ marginBottom: '16px' }}>Management Tools</h2>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card
            hoverable
            onClick={() => navigate('/tools')}
            style={{ cursor: 'pointer' }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <AppstoreOutlined style={{ fontSize: '24px', color: '#1890ff' }} />
              <h3 style={{ margin: 0 }}>Tools Library</h3>
              <p style={{ margin: 0, color: '#666', fontSize: '12px' }}>
                Manage and configure tools
              </p>
              <Button type="link" icon={<ArrowRightOutlined />} size="small">
                Go to Tools
              </Button>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card
            hoverable
            onClick={() => navigate('/providers')}
            style={{ cursor: 'pointer' }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <ApiOutlined style={{ fontSize: '24px', color: '#52c41a' }} />
              <h3 style={{ margin: 0 }}>LLM Providers</h3>
              <p style={{ margin: 0, color: '#666', fontSize: '12px' }}>
                Configure LLM integrations
              </p>
              <Button type="link" icon={<ArrowRightOutlined />} size="small">
                Go to Providers
              </Button>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card
            hoverable
            onClick={() => navigate('/')}
            style={{ cursor: 'pointer' }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <FileTextOutlined style={{ fontSize: '24px', color: '#faad14' }} />
              <h3 style={{ margin: 0 }}>Documentation</h3>
              <p style={{ margin: 0, color: '#666', fontSize: '12px' }}>
                Learn more about features
              </p>
              <Button type="link" icon={<ArrowRightOutlined />} size="small">
                Read Docs
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
