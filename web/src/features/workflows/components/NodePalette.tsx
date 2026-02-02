/**
 * Node Palette - Node Component Library
 * Neoclassical Design System
 *
 * Displays available workflow nodes as "Instruments" or "Components"
 * that can be dragged onto the drafting table.
 */

import React from 'react';
import { Alert, Spin, Tooltip } from 'antd';
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
  GlobalOutlined,
  MessageOutlined,
  ApartmentOutlined,
  PictureOutlined,
  SoundOutlined,
  BranchesOutlined,
  CodeOutlined,
  FileTextOutlined,
  ToolOutlined,
  DatabaseOutlined,
  FileOutlined,
  BellOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { nodeTypeConfigs } from '../utils/nodeUtils';
import { getWorkflowCapabilities } from '../api/workflowsApi';
import styles from '../styles/drafting.module.css';

interface NodePaletteProps {
  onAddNode: (type: string) => void;
}

const iconMap: Record<string, React.ReactNode> = {
  Play: <PlayCircleOutlined />,
  Square: <CheckCircleOutlined />,
  Globe: <GlobalOutlined />,
  MessageSquare: <MessageOutlined />,
  Layers: <ApartmentOutlined />,
  Image: <PictureOutlined />,
  Music: <SoundOutlined />,
  GitBranch: <BranchesOutlined />,
  Code: <CodeOutlined />,
  FileText: <FileTextOutlined />,
  Wrench: <ToolOutlined />,
  Database: <DatabaseOutlined />,
  File: <FileOutlined />,
  Bell: <BellOutlined />,
  Repeat: <ReloadOutlined />,
};

export default function NodePalette({ onAddNode }: NodePaletteProps) {
  const {
    data: capabilities,
    isLoading: capabilitiesLoading,
    error: capabilitiesError,
  } = useQuery({
    queryKey: ['workflows', 'capabilities'],
    queryFn: getWorkflowCapabilities,
    staleTime: 60_000,
  });

  const handleDragStart = (
    event: React.DragEvent<HTMLDivElement>,
    nodeType: string
  ) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  if (capabilitiesLoading) {
    return (
      <div className={styles.paletteContainer} style={{ padding: 16 }}>
        <Spin />
      </div>
    );
  }

  if (capabilitiesError || !capabilities) {
    return (
      <div className={styles.paletteContainer} style={{ padding: 16 }}>
        <Alert
          type="error"
          showIcon
          message="Capabilities unavailable"
          description="无法加载 /api/workflows/capabilities（fail-closed：节点面板不可用）。"
        />
      </div>
    );
  }

  const enabledTypes = new Set(
    (capabilities.node_types ?? [])
      .filter((item) => item.executor_available)
      .map((item) => item.type)
  );
  const visibleNodeConfigs = nodeTypeConfigs.filter((config) => enabledTypes.has(config.type));

  return (
    <div className={styles.paletteContainer}>
      <div style={{ padding: '16px', borderBottom: '1px solid var(--neo-border)' }}>
        <h3 style={{ margin: 0, fontFamily: 'var(--font-family-serif)', color: 'var(--neo-gold)' }}>
          Instruments
        </h3>
        <p style={{ margin: 0, fontSize: '10px', color: 'var(--neo-text-2)', textTransform: 'uppercase' }}>
          Node Component Library
        </p>
      </div>
      <div style={{ padding: '12px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {visibleNodeConfigs.map((config) => (
          <Tooltip key={config.type} title={config.description} placement="right">
            <div
              draggable
              onDragStart={(e) => handleDragStart(e, config.type)}
              onClick={() => onAddNode(config.type)}
              data-testid={`node-palette-item-${config.type}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px',
                borderRadius: '6px',
                border: '1px solid var(--neo-border)',
                background: 'var(--neo-surface-2)',
                cursor: 'grab',
                transition: 'all 0.2s',
                borderLeft: `3px solid ${config.color}`,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--neo-gold)';
                e.currentTarget.style.background = 'var(--neo-surface-1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--neo-border)';
                e.currentTarget.style.background = 'var(--neo-surface-2)';
              }}
            >
              <div
                style={{
                  width: 24,
                  height: 24,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: config.color,
                  fontSize: 16,
                }}
              >
                {iconMap[config.icon]}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--neo-text)'
                }}>
                  {config.label}
                </div>
              </div>
            </div>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}
