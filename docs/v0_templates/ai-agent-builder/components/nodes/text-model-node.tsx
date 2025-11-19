"use client"

import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { MessageSquare, Settings } from "lucide-react"
import { Card } from "@/components/ui/card"
import { getStatusColor } from "@/lib/node-utils"

export type TextModelNodeData = {
  model: string
  temperature: number
  maxTokens: number
  prompt?: string
  status?: "idle" | "running" | "completed" | "error"
  structuredOutput?: boolean
  schema?: string
  schemaName?: string
  output?: any
}

function TextModelNode({ data, selected }: NodeProps<TextModelNodeData>) {
  const status = data.status || "idle"

  return (
    <Card className={`min-w-[280px] max-w-[400px] border-2 bg-card transition-all ${getStatusColor(status, selected)}`}>
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary">
          <MessageSquare className="h-4 w-4 text-primary-foreground" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-foreground">Text Model</h3>
          <p className="text-xs text-muted-foreground">{data.model || "openai/gpt-5"}</p>
        </div>
        <Settings className="h-4 w-4 text-muted-foreground" />
      </div>

      <div className="space-y-2 p-4">
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Temperature:</span>
          <span className="font-mono text-foreground">{data.temperature || 0.7}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Max Tokens:</span>
          <span className="font-mono text-foreground">{data.maxTokens || 2000}</span>
        </div>
        {data.structuredOutput && (
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Structured:</span>
            <span className="font-mono text-foreground">{data.schemaName || "Yes"}</span>
          </div>
        )}
        {status === "running" && (
          <div className="flex items-center gap-2 text-xs text-yellow-600">
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
              {typeof data.output === "object" && data.output.text
                ? data.output.text
                : typeof data.output === "string"
                  ? data.output
                  : JSON.stringify(data.output, null, 2)}
            </p>
          </div>
        </div>
      )}

      <Handle type="target" position={Position.Left} id="prompt" className="!bg-primary" />
      <Handle type="source" position={Position.Right} id="output" className="!bg-primary" />
    </Card>
  )
}

export default memo(TextModelNode)
