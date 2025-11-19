"use client"

import { useState } from "react"
import type { Node, Edge } from "@xyflow/react"
import { Copy, Check, Download } from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { generateAISDKCode, generateRouteHandlerCode } from "@/lib/code-generator"

type CodeExportDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  nodes: Node[]
  edges: Edge[]
}

export function CodeExportDialog({ open, onOpenChange, nodes, edges }: CodeExportDialogProps) {
  const [copied, setCopied] = useState(false)

  const workflowCode = generateAISDKCode(nodes, edges)
  const routeHandlerCode = generateRouteHandlerCode(nodes, edges)

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = (code: string, filename: string) => {
    const blob = new Blob([code], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Export AI SDK Code</DialogTitle>
          <DialogDescription>Copy or download the generated code for your AI workflow</DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="workflow" className="w-full flex-1 flex flex-col min-h-0">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="workflow">Workflow Function</TabsTrigger>
            <TabsTrigger value="route">Route Handler</TabsTrigger>
          </TabsList>

          <TabsContent value="workflow" className="space-y-4 flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">Standalone workflow function</p>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => handleCopy(workflowCode)}>
                  {copied ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
                  {copied ? "Copied!" : "Copy"}
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleDownload(workflowCode, "workflow.ts")}>
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </Button>
              </div>
            </div>
            <pre className="flex-1 overflow-auto rounded-lg border border-border bg-secondary p-4 min-h-0">
              <code className="text-xs font-mono text-foreground whitespace-pre-wrap break-words">{workflowCode}</code>
            </pre>
          </TabsContent>

          <TabsContent value="route" className="space-y-4 flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">Next.js API route handler</p>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => handleCopy(routeHandlerCode)}>
                  {copied ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
                  {copied ? "Copied!" : "Copy"}
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleDownload(routeHandlerCode, "route.ts")}>
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </Button>
              </div>
            </div>
            <pre className="flex-1 overflow-auto rounded-lg border border-border bg-secondary p-4 min-h-0">
              <code className="text-xs font-mono text-foreground whitespace-pre-wrap break-words">
                {routeHandlerCode}
              </code>
            </pre>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
