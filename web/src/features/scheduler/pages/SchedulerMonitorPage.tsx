/**
 * Scheduler Monitor Page
 *
 * Real-time monitoring dashboard for the scheduler:
 * 1. Scheduler status and running state
 * 2. Total jobs in scheduler
 * 3. Active scheduled workflows vs disabled
 * 4. Job execution details
 * 5. Auto-refresh metrics every 5 seconds
 *
 * Implementation (GREEN phase)
 */

import { useState, useEffect } from 'react';
import {
  Row,
  Col,
  Card,
  Statistic,
  Table,
  Spin,
  Alert,
  Tag,
  Divider,
  Space,
  Button,
  Progress,
} from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  StopOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import * as schedulerApi from '../api/schedulerApi';
import type { SchedulerStatus, SchedulerJobs } from '../../../types/workflow';
import './SchedulerMonitorPage.css';

export default function SchedulerMonitorPage() {
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Get scheduler status with auto-refresh
  const {
    data: status,
    isLoading: statusLoading,
    error: statusError,
    refetch: refetchStatus,
  } = useQuery({
    queryKey: ['schedulerStatus'],
    queryFn: async () => {
      const response = await schedulerApi.getSchedulerStatus();
      return response.data as SchedulerStatus;
    },
    refetchInterval: autoRefresh ? 5000 : false,
  });

  // Get scheduler jobs with auto-refresh
  const {
    data: jobs,
    isLoading: jobsLoading,
    error: jobsError,
    refetch: refetchJobs,
  } = useQuery({
    queryKey: ['schedulerJobs'],
    queryFn: async () => {
      const response = await schedulerApi.getSchedulerJobs();
      return response.data as SchedulerJobs;
    },
    refetchInterval: autoRefresh ? 5000 : false,
  });

  const handleRefresh = () => {
    refetchStatus();
    refetchJobs();
  };

  const jobColumns = [
    {
      title: 'Job ID',
      dataIndex: 'id',
      key: 'id',
      width: '20%',
    },
    {
      title: 'Job Name',
      dataIndex: 'name',
      key: 'name',
      width: '20%',
    },
    {
      title: 'Trigger',
      dataIndex: 'trigger',
      key: 'trigger',
      width: '20%',
    },
    {
      title: 'Next Run Time',
      dataIndex: 'nextRunTime',
      key: 'nextRunTime',
      width: '20%',
      render: (time: string | undefined) => time ? new Date(time).toLocaleString() : '-',
    },
  ];

  const workflowColumns = [
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
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Last Execution',
      dataIndex: 'lastExecutionStatus',
      key: 'lastExecutionStatus',
      width: '15%',
      render: (status: string | undefined) =>
        status ? (
          <Tag color={status === 'success' ? 'green' : 'red'}>
            {status.toUpperCase()}
          </Tag>
        ) : (
          '-'
        ),
    },
    {
      title: 'In Scheduler',
      dataIndex: 'isInScheduler',
      key: 'isInScheduler',
      width: '10%',
      render: (isInScheduler: boolean) => (
        <Tag color={isInScheduler ? 'green' : 'orange'}>
          {isInScheduler ? 'YES' : 'NO'}
        </Tag>
      ),
    },
  ];

  const isLoading = statusLoading || jobsLoading;
  const hasError = statusError || jobsError;

  return (
    <div className="scheduler-monitor-page">
      {/* Header with controls */}
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col span={24}>
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={handleRefresh}
              loading={isLoading}
            >
              Refresh
            </Button>
            <Button
              type={autoRefresh ? 'primary' : 'default'}
              onClick={() => setAutoRefresh(!autoRefresh)}
            >
              {autoRefresh ? 'Auto-Refresh ON' : 'Auto-Refresh OFF'}
            </Button>
          </Space>
        </Col>
      </Row>

      {/* Error Alert */}
      {hasError && (
        <Alert
          message="Error loading scheduler information"
          type="error"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      {/* Loading */}
      {isLoading && !status && !jobs ? (
        <Spin size="large" />
      ) : (
        <>
          {/* Key Statistics */}
          <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Scheduler Status"
                  value={status?.schedulerRunning ? 'Running' : 'Stopped'}
                  prefix={
                    status?.schedulerRunning ? (
                      <CheckCircleOutlined style={{ color: '#52c41a' }} />
                    ) : (
                      <StopOutlined style={{ color: '#f5222d' }} />
                    )
                  }
                  valueStyle={{
                    color: status?.schedulerRunning ? '#52c41a' : '#f5222d',
                  }}
                />
              </Card>
            </Col>

            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Jobs in Scheduler"
                  value={status?.totalJobsInScheduler || 0}
                  prefix={<ClockCircleOutlined />}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>

            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Active Workflows"
                  value={jobs?.summary.totalActiveWorkflows || 0}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>

            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="Not in Scheduler"
                  value={jobs?.summary.workflowsNotInScheduler || 0}
                  valueStyle={{ color: '#faad14' }}
                />
              </Card>
            </Col>
          </Row>

          {/* Jobs Table */}
          <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
            <Col span={24}>
              <Card title="Jobs in Scheduler" bordered={false}>
                {status?.jobDetails && status.jobDetails.length > 0 ? (
                  <Table
                    columns={jobColumns}
                    dataSource={status.jobDetails.map((job) => ({
                      ...job,
                      key: job.id,
                    }))}
                    pagination={{ pageSize: 5 }}
                    size="small"
                  />
                ) : (
                  <div style={{ textAlign: 'center', padding: '20px' }}>
                    No jobs in scheduler
                  </div>
                )}
              </Card>
            </Col>
          </Row>

          <Divider />

          {/* Active Workflows Table */}
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card title="Active Scheduled Workflows" bordered={false}>
                {jobs?.activeScheduledWorkflows && jobs.activeScheduledWorkflows.length > 0 ? (
                  <Table
                    columns={workflowColumns}
                    dataSource={jobs.activeScheduledWorkflows.map((wf) => ({
                      ...wf,
                      key: wf.id,
                    }))}
                    pagination={{ pageSize: 10 }}
                    size="small"
                  />
                ) : (
                  <div style={{ textAlign: 'center', padding: '20px' }}>
                    No active scheduled workflows
                  </div>
                )}
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
}
