"use client"

import type React from "react"
import { MessageSquare, Layers, Wrench, FileText, ImageIcon, Code, Play, Flag, GitBranch, Globe } from "lucide-react"
import { Card } from "@/components/ui/card"

type NodeType = {
  type: string
  label: string
  icon: React.ReactNode
  color: string
  description: string
}

const nodeTypes: NodeType[] = [
  {
    type: "start",
    label: "Start",
    icon: <Play className="h-4 w-4" />,
    color: "bg-green-500",
    description: "Workflow entry point",
  },
  {
    type: "prompt",
    label: "Prompt",
    icon: <FileText className="h-4 w-4" />,
    color: "bg-chart-5",
    description: "Input text or prompt",
  },
  {
    type: "textModel",
    label: "Text Model",
    icon: <MessageSquare className="h-4 w-4" />,
    color: "bg-primary",
    description: "Generate text with LLM",
  },
  {
    type: "imageGeneration",
    label: "Image Generation",
    icon: <ImageIcon className="h-4 w-4" />,
    color: "bg-chart-1",
    description: "Generate images",
  },
  {
    type: "httpRequest",
    label: "HTTP Request",
    icon: <Globe className="h-4 w-4" />,
    color: "bg-blue-500",
    description: "Call external APIs",
  },
  {
    type: "conditional",
    label: "Conditional",
    icon: <GitBranch className="h-4 w-4" />,
    color: "bg-purple-500",
    description: "Branch based on condition",
  },
  {
    type: "javascript",
    label: "JavaScript",
    icon: <Code className="h-4 w-4" />,
    color: "bg-yellow-500",
    description: "Execute custom JS code",
  },
  {
    type: "embeddingModel",
    label: "Embedding Model",
    icon: <Layers className="h-4 w-4" />,
    color: "bg-chart-2",
    description: "Convert text to embeddings",
  },
  {
    type: "tool",
    label: "Tool",
    icon: <Wrench className="h-4 w-4" />,
    color: "bg-chart-4",
    description: "Custom function tool",
  },
  {
    type: "end",
    label: "End",
    icon: <Flag className="h-4 w-4" />,
    color: "bg-red-500",
    description: "Workflow output",
  },
]

type NodePaletteProps = {
  onAddNode: (type: string) => void
  onClose?: () => void
}

export function NodePalette({ onAddNode, onClose }: NodePaletteProps) {
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData("application/reactflow", nodeType)
    event.dataTransfer.effectAllowed = "move"
  }

  const handleAddNode = (type: string) => {
    onAddNode(type)
    onClose?.()
  }

  return (
    <aside className="h-full w-80 overflow-y-auto border-r border-border bg-card p-3 md:w-64 md:p-4">
      <h2 className="mb-3 text-sm font-semibold text-foreground md:mb-4">Node Palette</h2>
      <div className="space-y-2">
        {nodeTypes.map((node) => (
          <Card
            key={node.type}
            draggable
            onDragStart={(e) => onDragStart(e, node.type)}
            onClick={() => handleAddNode(node.type)}
            className="cursor-grab border border-border bg-secondary p-2 transition-all hover:border-primary hover:bg-secondary/80 active:cursor-grabbing md:p-3"
          >
            <div className="flex items-center gap-2 md:gap-3">
              <div className={`flex h-7 w-7 items-center justify-center rounded-md md:h-8 md:w-8 ${node.color}`}>
                <div className="text-primary-foreground">{node.icon}</div>
              </div>
              <div className="flex-1">
                <h3 className="text-xs font-medium text-foreground md:text-sm">{node.label}</h3>
                <p className="hidden text-xs text-muted-foreground md:block">{node.description}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </aside>
  )
}
