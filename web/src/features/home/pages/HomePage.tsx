/**
 * Home Page - 首页
 *
 * 参考 skal-ventures-template 设计
 * 包含：
 * - 粒子背景效果
 * - Hero 区域
 * - 工作流编辑器入口（突出显示）
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from 'antd';
import { RocketOutlined, GithubOutlined } from '@ant-design/icons';
import './HomePage.css';

export const HomePage = () => {
  const navigate = useNavigate();
  const [hovering, setHovering] = useState(false);

  const handleWorkflowEditor = () => {
    // 暂时导航到测试工作流
    navigate('/workflows/test-workflow-id/edit');
  };

  const handleGithubLogin = () => {
    // TODO: 实现 GitHub OAuth 登录
    console.log('GitHub Login');
  };

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

          {/* 中间导航 */}
          <nav className="home-nav">
            <a href="#features" className="home-nav-link">功能</a>
            <a href="#workflow" className="home-nav-link home-nav-link-highlight">工作流编辑器</a>
            <a href="#about" className="home-nav-link">关于</a>
            <a href="#contact" className="home-nav-link">联系</a>
          </nav>

          {/* GitHub 登录 */}
          <Button
            type="text"
            icon={<GithubOutlined />}
            onClick={handleGithubLogin}
            className="github-login-btn"
          >
            登录
          </Button>
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

          {/* 次要 CTA */}
          <Button
            size="large"
            onClick={handleWorkflowEditor}
            className="home-secondary-btn"
          >
            查看示例
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
