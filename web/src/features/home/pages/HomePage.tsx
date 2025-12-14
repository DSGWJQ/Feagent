/**
 * Home Page - 首页
 *
 * 设计：
 * - 顶部横向主导航（Agent管理、工作流、调度器、LLM管理）
 * - Hero 区域（主标题 + 开始构建工作流按钮）
 * - 石质背景效果
 * - NeoCard 展示特性
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Dropdown } from 'antd';
import type { MenuProps } from 'antd';
import {
  RocketOutlined,
  RobotOutlined,
  ClockCircleOutlined,
  ApiOutlined,
  DownOutlined,
  BookOutlined,
} from '@ant-design/icons';
import { NeoCard } from '@/shared/components/common/NeoCard';
import styles from './HomePage.module.css';

export const HomePage = () => {
  const navigate = useNavigate();
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [hovering, setHovering] = useState(false);

  const handleCreateAgent = () => {
    navigate('/agents/create');
  };

  const handleKnowledgeUpload = () => {
    navigate('/knowledge/upload');
  };

  // Agent 管理下拉菜单
  const agentMenuItems: MenuProps['items'] = [
    {
      key: '/app/agents',
      label: 'Agent 列表',
      onClick: () => navigate('/app/agents'),
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
    <div className={styles.container}>
      {/* 顶部导航 */}
      <header className={styles.header}>
        <div className={styles.headerContent}>
          {/* Logo */}
          <div className={styles.logo}>
            <RocketOutlined style={{ fontSize: '24px', color: 'var(--neo-gold)' }} />
            <span className={styles.logoText}>AI Agent Platform</span>
          </div>

          {/* 主导航菜单 */}
          <nav className={styles.nav}>
            {/* Agent 管理 */}
            <Dropdown menu={{ items: agentMenuItems }} placement="bottom">
              <Button type="text" className={styles.navBtn}>
                <RobotOutlined />
                Agent 管理
                <DownOutlined style={{ fontSize: '12px' }} />
              </Button>
            </Dropdown>

            {/* 调度器 */}
            <Dropdown menu={{ items: schedulerMenuItems }} placement="bottom">
              <Button type="text" className={styles.navBtn}>
                <ClockCircleOutlined />
                调度器
                <DownOutlined style={{ fontSize: '12px' }} />
              </Button>
            </Dropdown>

            {/* LLM 管理 */}
            <Dropdown menu={{ items: llmMenuItems }} placement="bottom">
              <Button type="text" className={styles.navBtn}>
                <ApiOutlined />
                LLM 管理
                <DownOutlined style={{ fontSize: '12px' }} />
              </Button>
            </Dropdown>

            <Button type="text" className={styles.navBtn} onClick={handleKnowledgeUpload}>
              <BookOutlined />
              上传知识库
            </Button>
          </nav>
        </div>
      </header>

      {/* Hero 区域 */}
      <div className={styles.hero}>
        <div className={styles.heroContent}>
          {/* Beta 标签 */}
          <div className={styles.betaPill}>
            <span className={styles.betaDot} />
            <span>BETA RELEASE</span>
          </div>

          {/* 主标题 */}
          <h1 className={styles.title}>
            构建你的
            <br />
            <i className={styles.titleItalic}>智能</i> 工作流
          </h1>

          {/* 副标题 */}
          <p className={styles.subtitle}>
            通过可视化拖拽编辑器，轻松创建强大的 AI 自动化工作流
          </p>

          {/* CTA 按钮 */}
          <Button
            type="primary"
            size="large"
            icon={<RocketOutlined />}
            onClick={handleCreateAgent}
            onMouseEnter={() => setHovering(true)}
            onMouseLeave={() => setHovering(false)}
            className={styles.ctaBtn}
          >
            开始构建工作流
          </Button>
        </div>
      </div>

      {/* 功能区域 */}
      <section id="features" className={styles.section}>
        <div className={styles.sectionContent}>
          <h2 className={styles.sectionTitle}>核心功能</h2>
          <div className={styles.featureGrid}>
            <NeoCard title="可视化编辑" variant="raised">
              <p>拖拽式工作流编辑器，直观易用</p>
            </NeoCard>
            <NeoCard title="AI 对话编辑" variant="raised">
              <p>通过自然语言描述，AI 自动生成工作流</p>
            </NeoCard>
            <NeoCard title="实时执行" variant="raised">
              <p>即时运行工作流，查看执行结果</p>
            </NeoCard>
          </div>
        </div>
      </section>

      {/* 工作流编辑器入口（突出显示） */}
      <section id="workflow" className={styles.workflowCtaSection}>
        <div className={styles.workflowCtaContent}>
          <h2 className={styles.workflowCtaTitle}>准备好开始了吗？</h2>
          <p className={styles.workflowCtaSubtitle}>立即体验强大的工作流编辑器</p>
          <Button
            type="primary"
            size="large"
            icon={<RocketOutlined />}
            onClick={handleCreateAgent}
            className={styles.ctaBtn}
          >
            进入工作流编辑器
          </Button>
        </div>
      </section>
    </div>
  );
};
