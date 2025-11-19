"use client"

import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { FileJson, Settings } from "lucide-react"
import { Card } from "@/components/ui/card"

export type StructuredOutputNodeData = {
  schemaName: string
  mode: "object" | "array"
}

function StructuredOutputNode({ data, selected }: NodeProps<StructuredOutputNodeData>) {
  return (
    <Card
      className={`min-w-[280px] border-2 bg-card transition-all ${
        selected ? "border-primary shadow-lg" : "border-border"
      }`}
    >
      <div className="flex items-center gap-3 border-b border-border bg-secondary/50 px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-chart-3">
          <FileJson className="h-4 w-4 text-primary-foreground" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-foreground">Structured Output</h3>
          <p className="text-xs text-muted-foreground">{data.schemaName || "Schema"}</p>
        </div>
        <Settings className="h-4 w-4 text-muted-foreground" />
      </div>

      <div className="space-y-2 p-4">
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Mode:</span>
          <span className="font-mono text-foreground">{data.mode || "object"}</span>
        </div>
      </div>

      <Handle type="target" position={Position.Left} id="input" className="!bg-chart-3" />
      <Handle type="source" position={Position.Right} id="output" className="!bg-chart-3" />
    </Card>
  )
}

export default memo(StructuredOutputNode)
