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
  PlusOutlined,
  EditOutlined,
  CalendarOutlined,
  DashboardOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import './MainLayout.css';

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
    getItem('创建 Agent', '/app/agents/create', <PlusOutlined />),
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
      {/* 侧边栏 */}
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={240}
        theme="light"
        className="main-layout-sider"
      >
        {/* Logo 区域 */}
        <div className="logo-container">
          <RobotOutlined className="logo-icon" />
          {!collapsed && <span className="logo-text">AI Agent</span>}
        </div>

        {/* 导航菜单 */}
        <Menu
          mode="inline"
          selectedKeys={getSelectedKeys()}
          defaultOpenKeys={getDefaultOpenKeys()}
          items={menuItems}
          onClick={handleMenuClick}
          className="main-layout-menu"
        />
      </Sider>

      {/* 右侧主内容区 */}
      <Layout>
        {/* 顶部栏 */}
        <Header className="main-layout-header">
          <div className="header-content">
            <div className="header-left">
              {/* 面包屑或页面标题可以放这里 */}
            </div>
            <div className="header-right">
              {/* 用户信息、通知等可以放这里 */}
              <span className="header-user">Admin</span>
            </div>
          </div>
        </Header>

        {/* 内容区域 */}
        <Content className="main-layout-content">
          <div className="content-wrapper">
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
