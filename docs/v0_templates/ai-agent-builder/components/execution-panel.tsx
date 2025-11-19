"use client"

import { useState } from "react"
import type { Node, Edge } from "@xyflow/react"
import { Play, X, CheckCircle, XCircle, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"

type ExecutionResult = {
  nodeId: string
  type: string
  output: any
  error?: string
}

type ExecutionPanelProps = {
  nodes: Node[]
  edges: Edge[]
  onClose: () => void
  onNodeStatusChange?: (nodeId: string, status: "idle" | "running" | "completed" | "error") => void
  onNodeOutputChange?: (nodeId: string, output: any) => void
}

export function ExecutionPanel({ nodes, edges, onClose, onNodeStatusChange, onNodeOutputChange }: ExecutionPanelProps) {
  const [isExecuting, setIsExecuting] = useState(false)
  const [executionLog, setExecutionLog] = useState<ExecutionResult[]>([])
  const [error, setError] = useState<string | null>(null)
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(null)

  const handleExecute = async () => {
    setIsExecuting(true)
    setExecutionLog([])
    setError(null)
    setCurrentNodeId(null)

    nodes.forEach((node) => {
      if (onNodeStatusChange) onNodeStatusChange(node.id, "idle")
      if (onNodeOutputChange) onNodeOutputChange(node.id, null)
    })

    try {
      const response = await fetch("/api/execute-workflow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nodes, edges }),
      })

      if (!response.body) {
        throw new Error("No response body")
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()

        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (!line.trim()) continue

          try {
            const update = JSON.parse(line)

            switch (update.type) {
              case "node_start":
                if (onNodeStatusChange && update.nodeId) {
                  onNodeStatusChange(update.nodeId, "running")
                  setCurrentNodeId(update.nodeId)
                }
                break

              case "node_complete":
                if (update.nodeId) {
                  if (onNodeStatusChange) {
                    onNodeStatusChange(update.nodeId, "completed")
                  }
                  if (onNodeOutputChange) {
                    onNodeOutputChange(update.nodeId, update.output)
                  }
                  const node = nodes.find((n) => n.id === update.nodeId)
                  setExecutionLog((prev) => [
                    ...prev,
                    {
                      nodeId: update.nodeId,
                      type: node?.type || "unknown",
                      output: update.output,
                    },
                  ])
                  setCurrentNodeId(null)
                }
                break

              case "node_error":
                if (update.nodeId && onNodeStatusChange) {
                  onNodeStatusChange(update.nodeId, "error")
                }
                const errorNode = nodes.find((n) => n.id === update.nodeId)
                setExecutionLog((prev) => [
                  ...prev,
                  {
                    nodeId: update.nodeId || "unknown",
                    type: errorNode?.type || "unknown",
                    output: null,
                    error: update.error,
                  },
                ])
                setCurrentNodeId(null)
                break

              case "complete":
                setCurrentNodeId(null)
                break

              case "error":
                setError(update.error || "Execution failed")
                break
            }
          } catch (parseError) {
            console.error("Failed to parse update:", parseError)
          }
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to execute workflow")
    } finally {
      setIsExecuting(false)
    }
  }

  const getNodeLabel = (nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId)
    if (!node) return nodeId

    switch (node.type) {
      case "textModel":
        return `Text Model (${node.data.model})`
      case "embeddingModel":
        return `Embedding Model (${node.data.model})`
      case "tool":
        return `Tool (${node.data.name})`
      case "structuredOutput":
        return `Structured Output (${node.data.schemaName})`
      case "prompt":
        return "Prompt"
      case "imageGeneration":
        return "Image Generation"
      case "audio":
        return "Audio Generation"
      case "javascript":
        return "JavaScript"
      default:
        return node.type || "Unknown"
    }
  }

  return (
    <aside className="absolute right-0 top-0 z-10 h-full w-full border-l border-border bg-card md:relative md:w-96">
      <div className="flex items-center justify-between border-b border-border p-4">
        <h2 className="text-sm font-semibold text-foreground">Execution</h2>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="p-4">
        <Button
          data-execute-workflow
          onClick={handleExecute}
          disabled={isExecuting || nodes.length === 0}
          className="w-full bg-primary hover:bg-primary/90"
        >
          {isExecuting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Executing...
            </>
          ) : (
            <>
              <Play className="mr-2 h-4 w-4" />
              Run Workflow
            </>
          )}
        </Button>

        {error && (
          <Card className="mt-4 border-destructive bg-destructive/10 p-3">
            <div className="flex items-start gap-2">
              <XCircle className="h-4 w-4 text-destructive" />
              <div className="flex-1">
                <p className="text-sm font-medium text-destructive">Error</p>
                <p className="text-xs text-destructive/80">{error}</p>
              </div>
            </div>
          </Card>
        )}

        {executionLog.length > 0 && (
          <div className="mt-4">
            <h3 className="mb-2 text-sm font-medium text-foreground">Execution Log</h3>
            <ScrollArea className="h-[calc(100vh-250px)]">
              <div className="space-y-3">
                {currentNodeId && (
                  <Card className="border border-primary/50 bg-primary/5 p-3">
                    <div className="flex items-start gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-foreground">{getNodeLabel(currentNodeId)}</p>
                        <p className="text-xs text-muted-foreground">Executing...</p>
                      </div>
                    </div>
                  </Card>
                )}
                {executionLog.map((result, index) => (
                  <Card
                    key={index}
                    className={`border p-3 ${
                      result.error ? "border-destructive bg-destructive/5" : "border-border bg-secondary/50"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {result.error ? (
                        <XCircle className="h-4 w-4 text-destructive" />
                      ) : (
                        <CheckCircle className="h-4 w-4 text-chart-3" />
                      )}
                      <div className="flex-1 space-y-1">
                        <p className="text-sm font-medium text-foreground">{getNodeLabel(result.nodeId)}</p>
                        {result.error ? (
                          <p className="text-xs text-destructive">{result.error}</p>
                        ) : (
                          <div className="rounded bg-background p-2">
                            <pre className="max-h-32 overflow-auto text-xs text-muted-foreground">
                              {typeof result.output === "string"
                                ? result.output
                                : JSON.stringify(result.output, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}

        {executionLog.length === 0 && currentNodeId && (
          <div className="mt-4">
            <h3 className="mb-2 text-sm font-medium text-foreground">Execution Log</h3>
            <Card className="border border-primary/50 bg-primary/5 p-3">
              <div className="flex items-start gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-foreground">{getNodeLabel(currentNodeId)}</p>
                  <p className="text-xs text-muted-foreground">Executing...</p>
                </div>
              </div>
            </Card>
          </div>
        )}

        {executionLog.length === 0 && !error && !isExecuting && !currentNodeId && (
          <Card className="mt-4 border-border bg-secondary/50 p-4">
            <p className="text-center text-sm text-muted-foreground">
              Click "Run Workflow" to execute your AI agent pipeline
            </p>
          </Card>
        )}
      </div>
    </aside>
  )
}
