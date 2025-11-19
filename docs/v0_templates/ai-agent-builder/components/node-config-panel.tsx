"use client"

import type { Node } from "@xyflow/react"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"

type NodeConfigPanelProps = {
  node: Node | null
  onClose: () => void
  onUpdate: (nodeId: string, data: any) => void
}

export function NodeConfigPanel({ node, onClose, onUpdate }: NodeConfigPanelProps) {
  if (!node) return null

  const handleUpdate = (field: string, value: any) => {
    onUpdate(node.id, { ...node.data, [field]: value })
  }

  const renderConfig = () => {
    switch (node.type) {
      case "start":
        return (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              The Start node marks the entry point of your workflow. No configuration needed.
            </p>
          </div>
        )

      case "end":
        return (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              The End node marks the final output of your workflow. No configuration needed.
            </p>
          </div>
        )

      case "conditional":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="condition">Condition (JavaScript)</Label>
              <Textarea
                id="condition"
                value={node.data.condition || ""}
                onChange={(e) => handleUpdate("condition", e.target.value)}
                placeholder="input1 === 'US'"
                rows={4}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Write a JavaScript expression that evaluates to true or false. Use input1, input2, etc. to reference
                connected node outputs.
              </p>
            </div>
          </div>
        )

      case "httpRequest":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="url">URL</Label>
              <Input
                id="url"
                value={node.data.url || ""}
                onChange={(e) => handleUpdate("url", e.target.value)}
                placeholder="https://api.example.com/endpoint"
              />
              <p className="text-xs text-muted-foreground">
                Use $input1, $input2, etc. to interpolate values in the URL
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="method">Method</Label>
              <Select value={node.data.method || "GET"} onValueChange={(value) => handleUpdate("method", value)}>
                <SelectTrigger id="method">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="GET">GET</SelectItem>
                  <SelectItem value="POST">POST</SelectItem>
                  <SelectItem value="PUT">PUT</SelectItem>
                  <SelectItem value="DELETE">DELETE</SelectItem>
                  <SelectItem value="PATCH">PATCH</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="headers">Headers (JSON)</Label>
              <Textarea
                id="headers"
                value={node.data.headers || ""}
                onChange={(e) => handleUpdate("headers", e.target.value)}
                placeholder='{"Content-Type": "application/json"}'
                rows={3}
                className="font-mono text-sm"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="body">Body (JSON)</Label>
              <Textarea
                id="body"
                value={node.data.body || ""}
                onChange={(e) => handleUpdate("body", e.target.value)}
                placeholder='{"key": "value"}'
                rows={4}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">Use $input1, $input2, etc. to interpolate values</p>
            </div>
          </div>
        )

      case "textModel":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="model">Model</Label>
              <Select value={node.data.model || "openai/gpt-5"} onValueChange={(value) => handleUpdate("model", value)}>
                <SelectTrigger id="model">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai/gpt-5">OpenAI GPT-5</SelectItem>
                  <SelectItem value="openai/gpt-5-mini">OpenAI GPT-5 Mini</SelectItem>
                  <SelectItem value="anthropic/claude-sonnet-4.5">Claude Sonnet 4.5</SelectItem>
                  <SelectItem value="xai/grok-4">xAI Grok 4</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="temperature">Temperature: {node.data.temperature || 0.7}</Label>
              <Slider
                id="temperature"
                min={0}
                max={2}
                step={0.1}
                value={[node.data.temperature || 0.7]}
                onValueChange={([value]) => handleUpdate("temperature", value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxTokens">Max Tokens</Label>
              <Input
                id="maxTokens"
                type="number"
                value={node.data.maxTokens || 2000}
                onChange={(e) => handleUpdate("maxTokens", Number.parseInt(e.target.value))}
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="structuredOutput"
                  checked={node.data.structuredOutput || false}
                  onChange={(e) => handleUpdate("structuredOutput", e.target.checked)}
                  className="h-4 w-4 rounded border-border"
                />
                <Label htmlFor="structuredOutput" className="cursor-pointer">
                  Structured Output
                </Label>
              </div>
            </div>

            {node.data.structuredOutput && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="schemaName">Schema Name</Label>
                  <Input
                    id="schemaName"
                    value={node.data.schemaName || ""}
                    onChange={(e) => handleUpdate("schemaName", e.target.value)}
                    placeholder="e.g., UserProfile"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="schema">Schema (Zod)</Label>
                  <Textarea
                    id="schema"
                    value={node.data.schema || ""}
                    onChange={(e) => handleUpdate("schema", e.target.value)}
                    placeholder="z.object({ name: z.string(), age: z.number() })"
                    rows={4}
                    className="font-mono text-sm"
                  />
                </div>
              </>
            )}
          </div>
        )

      case "embeddingModel":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="model">Model</Label>
              <Select
                value={node.data.model || "openai/text-embedding-3-small"}
                onValueChange={(value) => handleUpdate("model", value)}
              >
                <SelectTrigger id="model">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai/text-embedding-3-small">OpenAI Embedding Small</SelectItem>
                  <SelectItem value="openai/text-embedding-3-large">OpenAI Embedding Large</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="dimensions">Dimensions</Label>
              <Input
                id="dimensions"
                type="number"
                value={node.data.dimensions || 1536}
                onChange={(e) => handleUpdate("dimensions", Number.parseInt(e.target.value))}
              />
            </div>
          </div>
        )

      case "imageGeneration":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="model">Model</Label>
              <Select
                value={node.data.model || "gemini-2.5-flash-image"}
                onValueChange={(value) => handleUpdate("model", value)}
              >
                <SelectTrigger id="model">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gemini-2.5-flash-image">Gemini 2.5 Flash Image</SelectItem>
                  <SelectItem value="openai/dall-e-3">DALL-E 3</SelectItem>
                  <SelectItem value="stability-ai/stable-diffusion">Stable Diffusion</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="aspectRatio">Aspect Ratio</Label>
              <Select
                value={node.data.aspectRatio || "1:1"}
                onValueChange={(value) => handleUpdate("aspectRatio", value)}
              >
                <SelectTrigger id="aspectRatio">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1:1">1:1 (Square)</SelectItem>
                  <SelectItem value="16:9">16:9 (Landscape)</SelectItem>
                  <SelectItem value="9:16">9:16 (Portrait)</SelectItem>
                  <SelectItem value="4:3">4:3</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="outputFormat">Output Format</Label>
              <Select
                value={node.data.outputFormat || "png"}
                onValueChange={(value) => handleUpdate("outputFormat", value)}
              >
                <SelectTrigger id="outputFormat">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="png">PNG</SelectItem>
                  <SelectItem value="jpg">JPG</SelectItem>
                  <SelectItem value="webp">WebP</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )

      case "audio":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="model">Model</Label>
              <Select value={node.data.model || "openai/tts-1"} onValueChange={(value) => handleUpdate("model", value)}>
                <SelectTrigger id="model">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai/tts-1">OpenAI TTS-1</SelectItem>
                  <SelectItem value="openai/tts-1-hd">OpenAI TTS-1 HD</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="voice">Voice</Label>
              <Select value={node.data.voice || "alloy"} onValueChange={(value) => handleUpdate("voice", value)}>
                <SelectTrigger id="voice">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="alloy">Alloy</SelectItem>
                  <SelectItem value="echo">Echo</SelectItem>
                  <SelectItem value="fable">Fable</SelectItem>
                  <SelectItem value="onyx">Onyx</SelectItem>
                  <SelectItem value="nova">Nova</SelectItem>
                  <SelectItem value="shimmer">Shimmer</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="speed">Speed: {node.data.speed || 1.0}</Label>
              <Slider
                id="speed"
                min={0.25}
                max={4.0}
                step={0.25}
                value={[node.data.speed || 1.0]}
                onValueChange={([value]) => handleUpdate("speed", value)}
              />
            </div>
          </div>
        )

      case "tool":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Tool Name</Label>
              <Input
                id="name"
                value={node.data.name || ""}
                onChange={(e) => handleUpdate("name", e.target.value)}
                placeholder="e.g., getWeather"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={node.data.description || ""}
                onChange={(e) => handleUpdate("description", e.target.value)}
                placeholder="Describe what this tool does..."
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="code">Implementation (JavaScript)</Label>
              <Textarea
                id="code"
                value={node.data.code || ""}
                onChange={(e) => handleUpdate("code", e.target.value)}
                placeholder="// Tool implementation&#10;async function execute(args) {&#10;  // Your code here&#10;  return result;&#10;}"
                rows={8}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">Write the JavaScript function that implements this tool</p>
            </div>
          </div>
        )

      case "structuredOutput":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="schemaName">Schema Name</Label>
              <Input
                id="schemaName"
                value={node.data.schemaName || ""}
                onChange={(e) => handleUpdate("schemaName", e.target.value)}
                placeholder="e.g., UserProfile"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="mode">Mode</Label>
              <Select value={node.data.mode || "object"} onValueChange={(value) => handleUpdate("mode", value)}>
                <SelectTrigger id="mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="object">Object</SelectItem>
                  <SelectItem value="array">Array</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )

      case "prompt":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="content">Prompt Content</Label>
              <Textarea
                id="content"
                value={node.data.content || ""}
                onChange={(e) => handleUpdate("content", e.target.value)}
                placeholder="Enter your prompt..."
                rows={6}
              />
              <p className="text-xs text-muted-foreground">
                Use $input1, $input2, etc. to reference outputs from connected nodes
              </p>
            </div>
          </div>
        )

      case "javascript":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="code">JavaScript Code</Label>
              <Textarea
                id="code"
                value={node.data.code || ""}
                onChange={(e) => handleUpdate("code", e.target.value)}
                placeholder="// Access inputs as input1, input2, etc.&#10;return input1.toUpperCase()"
                rows={10}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Access connected node outputs as input1, input2, etc. Return a value to pass to the next node.
              </p>
            </div>
          </div>
        )

      default:
        return <p className="text-sm text-muted-foreground">No configuration available</p>
    }
  }

  return (
    <aside className="absolute right-0 top-0 z-10 h-full w-full border-l border-border bg-card md:relative md:w-80">
      <div className="flex items-center justify-between border-b border-border p-4">
        <h2 className="text-sm font-semibold text-foreground">Node Configuration</h2>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="overflow-y-auto p-4" style={{ height: "calc(100% - 57px)" }}>
        {renderConfig()}
      </div>
    </aside>
  )
}
