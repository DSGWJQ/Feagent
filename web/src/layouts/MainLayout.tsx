/**
 * MainLayout - 主布局组件
 *
 * 功能：
 * - 侧边栏导航菜单
 * - 顶部栏（logo + 用户信息）
 * - 内容区域（渲染子页面）
 * - 响应式折叠
 *
 * 设计原则：
 * - 遵循 Ant Design Pro 风格
 * - 支持菜单折叠/展开
 * - 高亮当前路由
 */

import { useState } from 'react';
import { Layout, Menu } from 'antd';
import type { MenuProps } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  RobotOutlined,
  ApartmentOutlined,
  ClockCircleOutlined,
  ApiOutlined,
  UnorderedListOutlined,
  EditOutlined,
  CalendarOutlined,
  DashboardOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useTheme } from '@/shared/contexts/ThemeContext';
import styles from './MainLayout.module.css';
import { ThemeToggle } from '@/shared/components/ThemeToggle';

const { Header, Sider, Content } = Layout;

/**
 * 菜单配置
 *
 * 结构说明：
 * - key: 路由路径（用于高亮当前菜单）
 * - icon: 图标
 * - label: 显示文本
 * - children: 子菜单
 */
type MenuItem = Required<MenuProps>['items'][number];

function getItem(
  label: React.ReactNode,
  key: React.Key,
  icon?: React.ReactNode,
  children?: MenuItem[],
): MenuItem {
  return {
    key,
    icon,
    children,
    label,
  } as MenuItem;
}

const menuItems: MenuItem[] = [
  getItem('Agent 管理', 'agents-group', <RobotOutlined />, [
    getItem('Agent 列表', '/app/agents', <UnorderedListOutlined />),
  ]),

  getItem('工作流管理', 'workflows-group', <ApartmentOutlined />, [
    getItem('工作流编辑器', '/workflows/test-workflow-id/edit', <EditOutlined />),
  ]),

  getItem('调度器', 'scheduler-group', <ClockCircleOutlined />, [
    getItem('定时任务', '/app/scheduled', <CalendarOutlined />),
    getItem('实时监控', '/app/monitor', <DashboardOutlined />),
  ]),

  getItem('LLM 管理', 'llm-group', <ApiOutlined />, [
    getItem('提供商管理', '/app/providers', <ThunderboltOutlined />),
  ]),
];

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const { theme } = useTheme();

  // 处理菜单点击
  const handleMenuClick: MenuProps['onClick'] = (e) => {
    // 如果点击的是分组项（有 -group 后缀），不导航
    if (e.key.toString().endsWith('-group')) {
      return;
    }
    navigate(e.key);
  };

  // 获取当前选中的菜单项
  const getSelectedKeys = () => {
    const path = location.pathname;

    // 特殊处理：/app/agents/:id 高亮 /app/agents
    if (path.match(/^\/app\/agents\/[^/]+$/)) {
      return ['/app/agents'];
    }

    // 特殊处理：/app/workflows/:id/edit 高亮工作流编辑器
    if (path.match(/^\/app\/workflows\/[^/]+\/edit$/)) {
      return ['/app/workflows/editor'];
    }

    return [path];
  };

  // 获取默认展开的菜单项
  const getDefaultOpenKeys = () => {
    const path = location.pathname;

    if (path.startsWith('/app/agents')) return ['agents-group'];
    if (path.startsWith('/app/workflows')) return ['workflows-group'];
    if (path.startsWith('/app/scheduled') || path.startsWith('/app/monitor')) {
      return ['scheduler-group'];
    }
    if (path.startsWith('/app/providers')) return ['llm-group'];

    return [];
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 侧边栏 - 添加 neoStone 质感 */}
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={256}
        theme={theme === 'dark' ? 'dark' : 'light'}
        className={styles.sider}
        trigger={null}
      >
        {/* Logo 区域 */}
        <div className={styles.logoContainer} onClick={() => setCollapsed(!collapsed)} style={{ cursor: 'pointer' }}>
          <RobotOutlined className={styles.logoIcon} />
          {!collapsed && <span className={styles.logoText}>AI Agent</span>}
        </div>

        {/* 导航菜单 */}
        <Menu
          mode="inline"
          selectedKeys={getSelectedKeys()}
          defaultOpenKeys={getDefaultOpenKeys()}
          items={menuItems}
          onClick={handleMenuClick}
          className={styles.menu}
          theme={theme === 'dark' ? 'dark' : 'light'}
        />
      </Sider>

      {/* 右侧主内容区 */}
      <Layout>
        {/* 顶部栏 */}
        <Header className={styles.header}>
          <div className={styles.headerContent}>
            <div className={styles.headerLeft}>
              {/* 这里未来可以放面包屑或通用的 PageTitle 占位 */}
            </div>
            <div className={styles.headerRight}>
              <ThemeToggle showTooltip={false} />
              <div className={styles.headerUser}>Admin</div>
            </div>
          </div>
        </Header>

        {/* 内容区域 - 去除强制的 Card 样式，由 PageShell 接管 */}
        <Content className={styles.content}>
          <div className={styles.contentWrapper}>
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
