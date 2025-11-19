"use client"

import { memo } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { ImageIcon } from "lucide-react"
import { Card } from "@/components/ui/card"
import { getStatusColor } from "@/lib/node-utils"

export type ImageGenerationNodeData = {
  model: string
  aspectRatio?: string
  outputFormat?: string
  status?: "idle" | "running" | "completed" | "error"
  output?: any
}

function ImageGenerationNode({ data, selected }: NodeProps<ImageGenerationNodeData>) {
  const status = data.status || "idle"

  return (
    <Card className={`min-w-[280px] max-w-[400px] border-2 bg-card transition-all ${getStatusColor(status, selected)}`}>
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-chart-1">
          <ImageIcon className="h-4 w-4 text-primary-foreground" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-foreground">Image Generation</h3>
          <p className="text-xs text-muted-foreground">Generate images</p>
        </div>
      </div>

      <div className="space-y-2 p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">Model</span>
          <span className="text-xs font-medium text-foreground">{data.model || "gemini-2.5-flash-image"}</span>
        </div>
        {data.aspectRatio && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Aspect Ratio</span>
            <span className="text-xs font-medium text-foreground">{data.aspectRatio}</span>
          </div>
        )}
        {status === "running" && (
          <div className="flex items-center gap-2 text-xs text-yellow-600">
            <div className="h-2 w-2 animate-pulse rounded-full bg-yellow-500" />
            Generating...
          </div>
        )}
      </div>

      {data.output && (
        <div className="border-t border-border bg-secondary/30 p-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Output:</p>
          {data.output.text && (
            <div className="mb-2 rounded bg-background p-2">
              <p className="text-xs text-foreground whitespace-pre-wrap break-words">{data.output.text}</p>
            </div>
          )}
          {data.output.images && data.output.images.length > 0 && (
            <div className="space-y-2">
              {data.output.images.map((imageDataUrl: string, idx: number) => (
                <img
                  key={idx}
                  src={imageDataUrl || "/placeholder.svg"}
                  alt={`Generated image ${idx + 1}`}
                  className="w-full rounded border border-border"
                  onError={(e) => {
                    console.error("[v0] Image failed to load:", imageDataUrl.substring(0, 50))
                    e.currentTarget.src = "/image-error.png"
                  }}
                />
              ))}
            </div>
          )}
        </div>
      )}

      <Handle type="target" position={Position.Left} id="prompt" className="!bg-chart-1" />
      <Handle type="source" position={Position.Right} id="image" className="!bg-chart-1" />
    </Card>
  )
}

export default memo(ImageGenerationNode)
