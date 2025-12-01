/**
 * Node Palette - 节点调色板
 *
 * 左侧面板，显示所有可用的节点类型，支持拖拽添加到画布
 */

import { Card, Tooltip } from 'antd';
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
import { nodeTypeConfigs } from '../utils/nodeUtils';

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
  const handleDragStart = (
    event: React.DragEvent<HTMLDivElement>,
    nodeType: string
  ) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      style={{
        width: 280,
        height: '100%',
        backgroundColor: '#141414', // 深色背景
        borderRight: '1px solid #262626',
        padding: 16,
        overflowY: 'auto',
      }}
    >
      <h3 style={{
        marginBottom: 16,
        fontSize: 16,
        fontWeight: 600,
        color: '#fafafa' // 浅色文字
      }}>
        节点调色板
      </h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {nodeTypeConfigs.map((config) => (
          <Tooltip key={config.type} title={config.description} placement="right">
            <Card
              size="small"
              hoverable
              draggable
              onDragStart={(e) => handleDragStart(e, config.type)}
              onClick={() => onAddNode(config.type)}
              style={{
                cursor: 'grab',
                borderLeft: `4px solid ${config.color}`,
                backgroundColor: '#1a1a1a', // 深色卡片背景
                borderColor: '#262626',
              }}
              styles={{
                body: {
                  padding: '8px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                },
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 6,
                  backgroundColor: config.color,
                  color: '#fff',
                  fontSize: 16,
                }}
              >
                {iconMap[config.icon]}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 14,
                  fontWeight: 500,
                  color: '#fafafa' // 浅色文字
                }}>
                  {config.label}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: '#8c8c8c', // 灰色描述文字
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {config.description}
                </div>
              </div>
            </Card>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}
