"use client"

import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { FileText } from "lucide-react"
import { Card } from "@/components/ui/card"
import { getStatusColor } from "@/lib/node-utils"

export type PromptNodeData = {
  content: string
  status?: "idle" | "running" | "completed" | "error"
  output?: any
}

function PromptNode({ data, selected }: NodeProps<PromptNodeData>) {
  const hasVariables = data.content?.includes("$input")
  const status = data.status || "idle"

  return (
    <Card className={`min-w-[280px] max-w-[400px] border-2 bg-card transition-all ${getStatusColor(status, selected)}`}>
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-chart-5">
          <FileText className="h-4 w-4 text-primary-foreground" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-foreground">Prompt</h3>
          <p className="text-xs text-muted-foreground">{hasVariables ? "Template with variables" : "Input text"}</p>
        </div>
      </div>

      <div className="p-4">
        <p className="line-clamp-3 text-xs text-muted-foreground">{data.content || "Enter your prompt..."}</p>
        {status === "running" && (
          <div className="mt-2 flex items-center gap-2 text-xs text-yellow-600">
            <div className="h-2 w-2 animate-pulse rounded-full bg-yellow-500" />
            Running...
          </div>
        )}
      </div>

      {data.output && (
        <div className="border-t border-border bg-secondary/30 p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Output:</p>
          <div className="rounded bg-background p-2 max-h-32 overflow-y-auto">
            <p className="text-xs text-foreground whitespace-pre-wrap break-words">
              {typeof data.output === "string" ? data.output : JSON.stringify(data.output, null, 2)}
            </p>
          </div>
        </div>
      )}

      <Handle type="target" position={Position.Left} id="input" className="!bg-chart-5" />
      <Handle type="source" position={Position.Right} id="output" className="!bg-chart-5" />
    </Card>
  )
}

export default memo(PromptNode)
