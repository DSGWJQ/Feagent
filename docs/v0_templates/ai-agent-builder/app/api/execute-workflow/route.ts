import { generateText } from "ai"
import { google } from "@ai-sdk/google"
import type { Node, Edge } from "@xyflow/react"

export const maxDuration = 30

type ExecutionResult = {
  nodeId: string
  type: string
  output: any
  error?: string
}

type StreamUpdate = {
  type: "node_start" | "node_complete" | "node_error" | "complete" | "error"
  nodeId?: string
  nodeType?: string
  output?: any
  error?: string
  executionLog?: ExecutionResult[]
}

function interpolateVariables(template: string, inputs: any[]): string {
  let result = template
  inputs.forEach((input, index) => {
    const placeholder = `$input${index + 1}`
    const value = typeof input === "string" ? input : JSON.stringify(input)
    result = result.replace(new RegExp(`\\${placeholder}`, "g"), value)
  })
  return result
}

export async function POST(req: Request) {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    async start(controller) {
      const sendUpdate = (update: StreamUpdate) => {
        controller.enqueue(encoder.encode(JSON.stringify(update) + "\n"))
      }

      try {
        const { nodes, edges }: { nodes: Node[]; edges: Edge[] } = await req.json()

        // Build execution graph
        const nodeMap = new Map(nodes.map((node) => [node.id, node]))
        const results = new Map<string, any>()
        const executionLog: ExecutionResult[] = []

        // Find nodes with no incoming edges (entry points)
        const incomingEdges = new Set(edges.map((e) => e.target))
        const entryNodes = nodes.filter((node) => !incomingEdges.has(node.id))

        // Execute nodes in topological order
        const executeNode = async (nodeId: string): Promise<any> => {
          // Return cached result if already executed
          if (results.has(nodeId)) {
            return results.get(nodeId)
          }

          const node = nodeMap.get(nodeId)
          if (!node) {
            throw new Error(`Node ${nodeId} not found`)
          }

          const inputEdges = edges
            .filter((e) => e.target === nodeId)
            .sort((a, b) => {
              const nodeA = nodeMap.get(a.source)
              const nodeB = nodeMap.get(b.source)
              return (nodeA?.position.x || 0) - (nodeB?.position.x || 0)
            })

          let hasValidInput = inputEdges.length === 0 // Nodes with no inputs are valid (entry nodes)

          for (const edge of inputEdges) {
            const sourceNode = nodeMap.get(edge.source)

            if (sourceNode?.type === "conditional") {
              // Check if the conditional has been evaluated
              if (results.has(edge.source)) {
                const conditionResult = results.get(edge.source)
                const expectedHandle = conditionResult ? "true" : "false"

                // If this edge's sourceHandle matches the condition result, it's a valid input
                if (!edge.sourceHandle || edge.sourceHandle === expectedHandle) {
                  hasValidInput = true
                  break
                }
              }
            } else {
              // For non-conditional inputs, check if the source node has executed successfully
              // First execute the source node to get its result
              const sourceResult = await executeNode(edge.source)
              // Only consider it valid input if the source node actually produced output
              if (sourceResult !== null) {
                hasValidInput = true
                break
              }
            }
          }

          // If no valid inputs, skip this node
          if (!hasValidInput) {
            results.set(nodeId, null)
            return null
          }

          sendUpdate({
            type: "node_start",
            nodeId,
            nodeType: node.type,
          })

          const inputs: any[] = []
          for (const edge of inputEdges) {
            // Only collect inputs from valid paths
            const sourceNode = nodeMap.get(edge.source)
            let shouldIncludeInput = true

            if (sourceNode?.type === "conditional" && results.has(edge.source)) {
              const conditionResult = results.get(edge.source)
              const expectedHandle = conditionResult ? "true" : "false"

              if (edge.sourceHandle && edge.sourceHandle !== expectedHandle) {
                shouldIncludeInput = false
              }
            }

            if (shouldIncludeInput) {
              const inputResult = await executeNode(edge.source)
              // Only add non-null inputs (skip inputs from skipped branches)
              if (inputResult !== null) {
                inputs.push(inputResult)
              }
            }
          }

          // Skip this node only if it has no valid inputs at all
          // (all inputs were null or from invalid conditional paths)
          if (inputEdges.length > 0 && inputs.length === 0) {
            results.set(nodeId, null)
            return null
          }

          let output: any

          try {
            switch (node.type) {
              case "start":
                output = "Workflow started"
                executionLog.push({
                  nodeId,
                  type: node.type,
                  output,
                })
                break

              case "end":
                const endInput = inputs.length > 0 ? inputs[0] : null
                output = endInput
                executionLog.push({
                  nodeId,
                  type: node.type,
                  output: {
                    finalOutput: output,
                  },
                })
                break

              case "conditional":
                const conditionCode = node.data.condition || "true"
                const conditionInputs = inputs

                try {
                  const func = new Function(
                    "inputs",
                    `
                    const input1 = inputs[0];
                    const input2 = inputs[1];
                    const input3 = inputs[2];
                    return ${conditionCode};
                  `,
                  )
                  const result = func(conditionInputs)
                  output = Boolean(result)
                } catch (condError: any) {
                  throw new Error(`Conditional evaluation error: ${condError.message}`)
                }

                executionLog.push({
                  nodeId,
                  type: node.type,
                  output: {
                    condition: conditionCode,
                    result: output,
                    inputs: conditionInputs,
                  },
                })
                break

              case "httpRequest":
                let url = node.data.url || ""
                const method = node.data.method || "GET"

                // Interpolate variables in URL
                if (inputs.length > 0) {
                  url = interpolateVariables(url, inputs)
                }

                const headers: Record<string, string> = {}
                if (node.data.headers) {
                  try {
                    Object.assign(headers, JSON.parse(node.data.headers))
                  } catch (e) {
                    console.error("Invalid headers JSON")
                  }
                }

                let body = node.data.body || ""
                if (body && inputs.length > 0) {
                  body = interpolateVariables(body, inputs)
                }

                const fetchOptions: RequestInit = {
                  method,
                  headers,
                }

                if (method !== "GET" && method !== "HEAD" && body) {
                  fetchOptions.body = body
                }

                try {
                  const response = await fetch(url, fetchOptions)
                  const data = await response.json()
                  output = data
                } catch (fetchError: any) {
                  throw new Error(`HTTP request failed: ${fetchError.message}`)
                }

                executionLog.push({
                  nodeId,
                  type: node.type,
                  output: {
                    url,
                    method,
                    response: output,
                  },
                })
                break

              case "prompt":
                const content = node.data.content || ""
                output = inputs.length > 0 ? interpolateVariables(content, inputs) : content
                executionLog.push({
                  nodeId,
                  type: node.type,
                  output,
                })
                break

              case "textModel":
                const prompt = inputs.length > 0 ? String(inputs[0]) : node.data.prompt || ""

                if (node.data.structuredOutput && node.data.schema) {
                  const textResult = await generateText({
                    model: node.data.model || "openai/gpt-5",
                    prompt: `${prompt}\n\nRespond in JSON format matching this schema: ${node.data.schema}`,
                    temperature: node.data.temperature || 0.7,
                    maxTokens: node.data.maxTokens || 2000,
                  })
                  output = textResult.text
                  executionLog.push({
                    nodeId,
                    type: node.type,
                    output: {
                      text: output,
                      structured: true,
                      schemaName: node.data.schemaName,
                      usage: textResult.usage,
                    },
                  })
                } else {
                  const textResult = await generateText({
                    model: node.data.model || "openai/gpt-5",
                    prompt: prompt,
                    temperature: node.data.temperature || 0.7,
                    maxTokens: node.data.maxTokens || 2000,
                  })
                  output = textResult.text
                  executionLog.push({
                    nodeId,
                    type: node.type,
                    output: {
                      text: output,
                      usage: textResult.usage,
                    },
                  })
                }
                break

              case "imageGeneration":
                const imagePrompt = inputs.length > 0 ? String(inputs[0]) : ""
                const imageResult = await generateText({
                  model: google(node.data.model || "gemini-2.5-flash-image"),
                  prompt: imagePrompt,
                })

                const images: string[] = []
                if (imageResult.files) {
                  for (const file of imageResult.files) {
                    if (file.mediaType.startsWith("image/")) {
                      const base64Data = file.base64
                      if (base64Data.startsWith("data:")) {
                        images.push(base64Data)
                      } else {
                        images.push(`data:${file.mediaType};base64,${base64Data}`)
                      }
                    }
                  }
                }

                output = images.length > 0 ? images[0] : "No image generated"
                executionLog.push({
                  nodeId,
                  type: node.type,
                  output: {
                    images,
                    prompt: imagePrompt,
                    text: imageResult.text,
                  },
                })
                break

              case "javascript":
                const jsCode = node.data.code || ""
                const jsInputs = inputs

                try {
                  const func = new Function(
                    "inputs",
                    `
                    const input1 = inputs[0];
                    const input2 = inputs[1];
                    const input3 = inputs[2];
                    const input4 = inputs[3];
                    const input5 = inputs[4];
                    ${jsCode}
                  `,
                  )
                  output = func(jsInputs)
                } catch (jsError: any) {
                  throw new Error(`JavaScript execution error: ${jsError.message}`)
                }

                executionLog.push({
                  nodeId,
                  type: node.type,
                  output,
                })
                break

              case "audio":
                const audioText = inputs.length > 0 ? String(inputs[0]) : ""
                output = {
                  audioUrl: "Audio generation placeholder",
                  text: audioText,
                  model: node.data.model,
                  voice: node.data.voice,
                }
                executionLog.push({
                  nodeId,
                  type: node.type,
                  output,
                })
                break

              case "embeddingModel":
                const embInput = inputs.length > 0 ? String(inputs[0]) : ""
                output = { embedding: "Embedding generation not implemented in demo" }
                executionLog.push({
                  nodeId,
                  type: node.type,
                  output,
                })
                break

              case "structuredOutput":
                const structInput = inputs.length > 0 ? String(inputs[0]) : ""
                output = { message: "Structured output not implemented in demo" }
                executionLog.push({
                  nodeId,
                  type: node.type,
                  output,
                })
                break

              case "tool":
                if (node.data.code) {
                  try {
                    const toolInputs = inputs
                    const func = new Function(
                      "inputs",
                      "args",
                      `
                      const input1 = inputs[0];
                      const input2 = inputs[1];
                      const input3 = inputs[2];
                      ${node.data.code}
                    `,
                    )
                    output = await func(toolInputs, {})
                  } catch (toolError: any) {
                    throw new Error(`Tool execution error: ${toolError.message}`)
                  }
                } else {
                  output = { message: "Tool has no implementation code" }
                }
                executionLog.push({
                  nodeId,
                  type: node.type,
                  output,
                })
                break

              default:
                output = null
            }

            results.set(nodeId, output)

            sendUpdate({
              type: "node_complete",
              nodeId,
              nodeType: node.type,
              output,
            })

            return output
          } catch (error: any) {
            const errorMessage = error.message || "Unknown error"
            executionLog.push({
              nodeId,
              type: node.type,
              output: null,
              error: errorMessage,
            })

            sendUpdate({
              type: "node_error",
              nodeId,
              nodeType: node.type,
              error: errorMessage,
            })

            throw error
          }
        }

        // Execute all entry nodes
        const finalResults: any[] = []
        for (const entryNode of entryNodes) {
          const result = await executeNode(entryNode.id)
          finalResults.push(result)

          // Also execute all downstream nodes
          const processDownstream = async (nodeId: string) => {
            const outgoingEdges = edges.filter((e) => e.source === nodeId)

            // The skip logic in executeNode will handle conditional branching
            for (const edge of outgoingEdges) {
              await executeNode(edge.target)
              await processDownstream(edge.target)
            }
          }
          await processDownstream(entryNode.id)
        }

        sendUpdate({
          type: "complete",
          executionLog,
        })

        controller.close()
      } catch (error: any) {
        sendUpdate({
          type: "error",
          error: error.message || "Execution failed",
        })
        controller.close()
      }
    },
  })

  return new Response(stream, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Transfer-Encoding": "chunked",
    },
  })
}
