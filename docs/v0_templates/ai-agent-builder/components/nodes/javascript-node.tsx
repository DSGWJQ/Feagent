"use client"

import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { Code, Settings } from "lucide-react"
import { Card } from "@/components/ui/card"
import { getStatusColor } from "@/lib/node-utils"

export type JavaScriptNodeData = {
  code: string
  status?: "idle" | "running" | "completed" | "error"
  output?: any
}

function JavaScriptNode({ data, selected }: NodeProps<JavaScriptNodeData>) {
  const status = data.status || "idle"

  return (
    <Card className={`min-w-[280px] max-w-[400px] border-2 bg-card transition-all ${getStatusColor(status, selected)}`}>
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-amber-500">
          <Code className="h-4 w-4 text-white" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-foreground">JavaScript</h3>
          <p className="text-xs text-muted-foreground">Execute custom code</p>
        </div>
        <Settings className="h-4 w-4 text-muted-foreground" />
      </div>

      <div className="p-4">
        <div className="rounded bg-background p-2">
          <pre className="text-xs text-muted-foreground overflow-x-auto max-h-20">
            {data.code || "// Enter JavaScript code..."}
          </pre>
        </div>
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

      <Handle type="target" position={Position.Left} id="input" className="!bg-amber-500" />
      <Handle type="source" position={Position.Right} id="output" className="!bg-amber-500" />
    </Card>
  )
}

export default memo(JavaScriptNode)
