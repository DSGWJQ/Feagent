"use client"

import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { GitBranch } from "lucide-react"
import { Card } from "@/components/ui/card"
import { getStatusColor } from "@/lib/node-utils"

export type ConditionalNodeData = {
  condition: string
  status?: "idle" | "running" | "completed" | "error"
  output?: any
}

function ConditionalNode({ data, selected }: NodeProps<ConditionalNodeData>) {
  const status = data.status || "idle"

  return (
    <Card className={`min-w-[280px] max-w-[400px] border-2 bg-card transition-all ${getStatusColor(status, selected)}`}>
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-purple-500">
          <GitBranch className="h-4 w-4 text-white" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-foreground">Conditional</h3>
          <p className="text-xs text-muted-foreground">Branch based on condition</p>
        </div>
      </div>

      <div className="space-y-2 p-4">
        <div className="text-xs">
          <span className="text-muted-foreground">Condition:</span>
          <div className="mt-1 rounded bg-secondary p-2 font-mono text-xs text-foreground">
            {data.condition || "input1 === 'value'"}
          </div>
        </div>
        {status === "running" && (
          <div className="flex items-center gap-2 text-xs text-yellow-600">
            <div className="h-2 w-2 animate-pulse rounded-full bg-yellow-500" />
            Evaluating...
          </div>
        )}
      </div>

      {data.output !== undefined && (
        <div className="border-t border-border bg-secondary/30 p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Result:</p>
          <div className="rounded bg-background p-2">
            <p className={`text-xs font-semibold ${data.output ? "text-green-600" : "text-red-600"}`}>
              {data.output ? "✓ TRUE" : "✗ FALSE"}
            </p>
          </div>
        </div>
      )}

      <Handle type="target" position={Position.Left} id="input" className="!bg-purple-500" />
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        className="!bg-green-500"
        style={{ top: "40%" }}
        title="TRUE path"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        className="!bg-red-500"
        style={{ top: "60%" }}
        title="FALSE path"
      />
    </Card>
  )
}

export default memo(ConditionalNode)
