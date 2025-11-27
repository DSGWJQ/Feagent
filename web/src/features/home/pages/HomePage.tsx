/**
 * Home Page - 首页
 *
 * 设计：
 * - 顶部横向主导航（Agent管理、工作流、调度器、LLM管理）
 * - Hero 区域（主标题 + 开始构建工作流按钮）
 * - 粒子背景效果
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Dropdown } from 'antd';
import type { MenuProps } from 'antd';
import {
  RocketOutlined,
  RobotOutlined,
  ApartmentOutlined,
  ClockCircleOutlined,
  ApiOutlined,
  DownOutlined,
} from '@ant-design/icons';
import './HomePage.css';

export const HomePage = () => {
  const navigate = useNavigate();
  const [hovering, setHovering] = useState(false);

  const handleWorkflowEditor = () => {
    // 导航到工作流编辑器（全屏，无侧边栏）
    navigate('/workflows/test-workflow-id/edit');
  };

  // Agent 管理下拉菜单
  const agentMenuItems: MenuProps['items'] = [
    {
      key: '/app/agents',
      label: 'Agent 列表',
      onClick: () => navigate('/app/agents'),
    },
    {
      key: '/app/agents/create',
      label: '创建 Agent',
      onClick: () => navigate('/app/agents/create'),
    },
  ];

  // 调度器下拉菜单
  const schedulerMenuItems: MenuProps['items'] = [
    {
      key: '/app/scheduled',
      label: '定时任务',
      onClick: () => navigate('/app/scheduled'),
    },
    {
      key: '/app/monitor',
      label: '实时监控',
      onClick: () => navigate('/app/monitor'),
    },
  ];

  // LLM 管理下拉菜单
  const llmMenuItems: MenuProps['items'] = [
    {
      key: '/app/providers',
      label: '提供商管理',
      onClick: () => navigate('/app/providers'),
    },
  ];

  return (
    <div className="home-page">
      {/* 粒子背景 */}
      <div className="particles-background" />

      {/* 顶部导航 */}
      <header className="home-header">
        <div className="home-header-content">
          {/* Logo */}
          <div className="home-logo">
            <RocketOutlined style={{ fontSize: '24px' }} />
            <span className="home-logo-text">AI Agent Platform</span>
          </div>

          {/* 主导航菜单 */}
          <nav className="home-nav">
            {/* Agent 管理 */}
            <Dropdown menu={{ items: agentMenuItems }} placement="bottom">
              <Button type="text" className="home-nav-btn">
                <RobotOutlined />
                Agent 管理
                <DownOutlined style={{ fontSize: '12px' }} />
              </Button>
            </Dropdown>

            {/* 工作流管理 */}
            <Button
              type="text"
              className="home-nav-btn"
              onClick={handleWorkflowEditor}
            >
              <ApartmentOutlined />
              工作流
            </Button>

            {/* 调度器 */}
            <Dropdown menu={{ items: schedulerMenuItems }} placement="bottom">
              <Button type="text" className="home-nav-btn">
                <ClockCircleOutlined />
                调度器
                <DownOutlined style={{ fontSize: '12px' }} />
              </Button>
            </Dropdown>

            {/* LLM 管理 */}
            <Dropdown menu={{ items: llmMenuItems }} placement="bottom">
              <Button type="text" className="home-nav-btn">
                <ApiOutlined />
                LLM 管理
                <DownOutlined style={{ fontSize: '12px' }} />
              </Button>
            </Dropdown>
          </nav>
        </div>
      </header>

      {/* Hero 区域 */}
      <div className="home-hero">
        <div className="home-hero-content">
          {/* Beta 标签 */}
          <div className="beta-pill">
            <span className="beta-dot" />
            <span>BETA RELEASE</span>
          </div>

          {/* 主标题 */}
          <h1 className="home-title">
            构建你的
            <br />
            <i className="home-title-italic">智能</i> 工作流
          </h1>

          {/* 副标题 */}
          <p className="home-subtitle">
            通过可视化拖拽编辑器，轻松创建强大的 AI 自动化工作流
          </p>

          {/* CTA 按钮 */}
          <Button
            type="primary"
            size="large"
            icon={<RocketOutlined />}
            onClick={handleWorkflowEditor}
            onMouseEnter={() => setHovering(true)}
            onMouseLeave={() => setHovering(false)}
            className={`home-cta-btn ${hovering ? 'hovering' : ''}`}
          >
            开始构建工作流
          </Button>
        </div>
      </div>

      {/* 功能区域 */}
      <section id="features" className="home-section">
        <div className="home-section-content">
          <h2 className="home-section-title">核心功能</h2>
          <div className="feature-grid">
            <div className="feature-card">
              <h3>可视化编辑</h3>
              <p>拖拽式工作流编辑器，直观易用</p>
            </div>
            <div className="feature-card">
              <h3>AI 对话编辑</h3>
              <p>通过自然语言描述，AI 自动生成工作流</p>
            </div>
            <div className="feature-card">
              <h3>实时执行</h3>
              <p>即时运行工作流，查看执行结果</p>
            </div>
          </div>
        </div>
      </section>

      {/* 工作流编辑器入口（突出显示） */}
      <section id="workflow" className="workflow-cta-section">
        <div className="workflow-cta-content">
          <h2 className="workflow-cta-title">准备好开始了吗？</h2>
          <p className="workflow-cta-subtitle">立即体验强大的工作流编辑器</p>
          <Button
            type="primary"
            size="large"
            icon={<RocketOutlined />}
            onClick={handleWorkflowEditor}
            className="workflow-cta-btn"
          >
            进入工作流编辑器
          </Button>
        </div>
      </section>
    </div>
  );
};
