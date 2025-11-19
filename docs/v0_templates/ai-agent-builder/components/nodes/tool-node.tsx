"use client"

import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { Wrench, Settings } from "lucide-react"
import { Card } from "@/components/ui/card"
import { getStatusColor } from "@/lib/node-utils"

export type ToolNodeData = {
  name: string
  description: string
  parameters?: Record<string, any>
  code?: string
  status?: "idle" | "running" | "completed" | "error"
}

function ToolNode({ data, selected }: NodeProps<ToolNodeData>) {
  const status = data.status || "idle"

  return (
    <Card className={`min-w-[280px] border-2 bg-card transition-all ${getStatusColor(status, selected)}`}>
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-chart-4">
          <Wrench className="h-4 w-4 text-primary-foreground" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-foreground">Tool</h3>
          <p className="text-xs text-muted-foreground">{data.name || "Custom Tool"}</p>
        </div>
        <Settings className="h-4 w-4 text-muted-foreground" />
      </div>

      <div className="p-4">
        <p className="text-xs text-muted-foreground">{data.description || "No description provided"}</p>
        {data.code && (
          <div className="mt-2 flex items-center gap-1 text-xs text-chart-3">
            <div className="h-1.5 w-1.5 rounded-full bg-chart-3" />
            Code implemented
          </div>
        )}
        {status === "running" && (
          <div className="mt-2 flex items-center gap-2 text-xs text-yellow-600">
            <div className="h-2 w-2 animate-pulse rounded-full bg-yellow-500" />
            Running...
          </div>
        )}
      </div>

      <Handle type="target" position={Position.Left} id="input" className="!bg-chart-4" />
      <Handle type="source" position={Position.Right} id="output" className="!bg-chart-4" />
    </Card>
  )
}

export default memo(ToolNode)
