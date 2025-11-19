"use client"

import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { Globe } from "lucide-react"
import { Card } from "@/components/ui/card"
import { getStatusColor } from "@/lib/node-utils"

export type HttpRequestNodeData = {
  url: string
  method: string
  headers?: string
  body?: string
  status?: "idle" | "running" | "completed" | "error"
  output?: any
}

function HttpRequestNode({ data, selected }: NodeProps<HttpRequestNodeData>) {
  const status = data.status || "idle"

  return (
    <Card className={`min-w-[280px] max-w-[400px] border-2 bg-card transition-all ${getStatusColor(status, selected)}`}>
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-500">
          <Globe className="h-4 w-4 text-white" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-foreground">HTTP Request</h3>
          <p className="text-xs text-muted-foreground">{data.method || "GET"}</p>
        </div>
      </div>

      <div className="space-y-2 p-4">
        <div className="text-xs">
          <span className="text-muted-foreground">URL:</span>
          <div className="mt-1 truncate rounded bg-secondary p-2 font-mono text-xs text-foreground">
            {data.url || "https://api.example.com"}
          </div>
        </div>
        {status === "running" && (
          <div className="flex items-center gap-2 text-xs text-yellow-600">
            <div className="h-2 w-2 animate-pulse rounded-full bg-yellow-500" />
            Requesting...
          </div>
        )}
      </div>

      {data.output && (
        <div className="border-t border-border bg-secondary/30 p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Response:</p>
          <div className="max-h-32 overflow-y-auto rounded bg-background p-2">
            <p className="whitespace-pre-wrap break-words text-xs text-foreground">
              {typeof data.output === "string" ? data.output : JSON.stringify(data.output, null, 2)}
            </p>
          </div>
        </div>
      )}

      <Handle type="target" position={Position.Left} id="input" className="!bg-blue-500" />
      <Handle type="source" position={Position.Right} id="output" className="!bg-blue-500" />
    </Card>
  )
}

export default memo(HttpRequestNode)
