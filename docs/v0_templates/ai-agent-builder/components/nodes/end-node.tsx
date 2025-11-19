"use client"

import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { Flag } from "lucide-react"
import { Card } from "@/components/ui/card"
import { getStatusColor } from "@/lib/node-utils"

export type EndNodeData = {
  status?: "idle" | "running" | "completed" | "error"
  output?: any
}

function EndNode({ data, selected }: NodeProps<EndNodeData>) {
  const status = data.status || "idle"

  const hasImages = () => {
    if (!data.output) return false
    if (Array.isArray(data.output)) {
      return data.output.some((item) => typeof item === "string" && item.startsWith("data:image/"))
    }
    return typeof data.output === "string" && data.output.startsWith("data:image/")
  }

  const getImages = () => {
    if (!data.output) return []
    if (Array.isArray(data.output)) {
      return data.output.filter((item) => typeof item === "string" && item.startsWith("data:image/"))
    }
    if (typeof data.output === "string" && data.output.startsWith("data:image/")) {
      return [data.output]
    }
    return []
  }

  return (
    <Card className={`min-w-[200px] border-2 bg-card transition-all ${getStatusColor(status, selected)}`}>
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-red-500">
          <Flag className="h-4 w-4 text-white" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-foreground">End</h3>
          <p className="text-xs text-muted-foreground">Workflow output</p>
        </div>
      </div>

      {data.output && (
        <div className="border-t border-border bg-secondary/30 p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Final Output:</p>
          {hasImages() ? (
            <div className="space-y-2">
              {getImages().map((img, idx) => (
                <img
                  key={idx}
                  src={img || "/placeholder.svg"}
                  alt={`Output ${idx + 1}`}
                  className="w-full rounded border border-border"
                />
              ))}
            </div>
          ) : (
            <div className="max-h-32 overflow-y-auto rounded bg-background p-2">
              <p className="whitespace-pre-wrap break-words text-xs text-foreground">
                {typeof data.output === "string" ? data.output : JSON.stringify(data.output, null, 2)}
              </p>
            </div>
          )}
        </div>
      )}

      <Handle type="target" position={Position.Left} id="input" className="!bg-red-500" />
    </Card>
  )
}

export default memo(EndNode)
