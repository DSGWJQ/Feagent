/**
 * 代码生成器
 * 
 * 将工作流转换为可执行的 Python 或 TypeScript 代码
 */

import type { Node, Edge } from '@xyflow/react';

/**
 * 生成 Python 代码
 */
export function generatePythonCode(nodes: Node[], edges: Edge[]): string {
  const imports = new Set<string>();
  imports.add('import asyncio');
  imports.add('from typing import Any, Dict');

  let code = '';

  // 为每个节点生成函数
  nodes.forEach((node) => {
    switch (node.type) {
      case 'start':
        code += `\nasync def node_${node.id}_start(context: Dict[str, Any]) -> Any:
    """Start node"""
    print("Starting workflow...")
    return context.get("initial_input", {})
`;
        break;

      case 'httpRequest':
        imports.add('import httpx');
        code += `\nasync def node_${node.id}_http_request(context: Dict[str, Any]) -> Any:
    """HTTP Request node"""
    url = "${node.data.url || 'https://api.example.com'}"
    method = "${node.data.method || 'GET'}"
    
    async with httpx.AsyncClient() as client:
        response = await client.request(method, url)
        return response.json()
`;
        break;

      case 'textModel':
        imports.add('from openai import AsyncOpenAI');
        code += `\nasync def node_${node.id}_text_model(context: Dict[str, Any]) -> Any:
    """Text Model node"""
    client = AsyncOpenAI()
    
    response = await client.chat.completions.create(
        model="${node.data.model || 'gpt-4'}",
        messages=[
            {"role": "user", "content": str(context.get("prompt", ""))}
        ],
        temperature=${node.data.temperature || 0.7},
        max_tokens=${node.data.maxTokens || 2000}
    )
    
    return response.choices[0].message.content
`;
        break;

      case 'conditional':
        code += `\nasync def node_${node.id}_conditional(context: Dict[str, Any]) -> Any:
    """Conditional node"""
    condition = ${node.data.condition || 'True'}
    return {"result": condition, "branch": "true" if condition else "false"}
`;
        break;

      case 'javascript':
        code += `\nasync def node_${node.id}_javascript(context: Dict[str, Any]) -> Any:
    """JavaScript node (Python equivalent)"""
    # Original JS code:
    # ${node.data.code?.replace(/\n/g, '\n    # ') || '// Your code here'}
    
    # TODO: Implement Python equivalent
    return context.get("input1")
`;
        break;

      case 'prompt':
        code += `\nasync def node_${node.id}_prompt(context: Dict[str, Any]) -> Any:
    """Prompt node"""
    return """${node.data.content || 'Enter your prompt...'}"""
`;
        break;

      case 'end':
        code += `\nasync def node_${node.id}_end(context: Dict[str, Any]) -> Any:
    """End node"""
    print("Workflow completed!")
    return context.get("final_result")
`;
        break;

      default:
        code += `\nasync def node_${node.id}_${node.type}(context: Dict[str, Any]) -> Any:
    """${node.type} node"""
    # TODO: Implement ${node.type} logic
    return context.get("input")
`;
    }
  });

  // 生成主执行函数
  code += `\n\nasync def execute_workflow(initial_input: Dict[str, Any]) -> Any:
    """Execute the workflow"""
    context = {"initial_input": initial_input}
    
`;

  // 按照边的顺序执行节点
  const startNode = nodes.find((n) => n.type === 'start');
  if (startNode) {
    code += `    # Execute nodes\n`;
    code += `    result = await node_${startNode.id}_start(context)\n`;
    code += `    context["node_${startNode.id}"] = result\n\n`;

    // 简单的顺序执行（实际应该根据边的连接关系）
    const otherNodes = nodes.filter((n) => n.type !== 'start' && n.type !== 'end');
    otherNodes.forEach((node) => {
      code += `    result = await node_${node.id}_${node.type}(context)\n`;
      code += `    context["node_${node.id}"] = result\n\n`;
    });

    const endNode = nodes.find((n) => n.type === 'end');
    if (endNode) {
      code += `    final_result = await node_${endNode.id}_end(context)\n`;
      code += `    return final_result\n`;
    }
  }

  code += `\n\nif __name__ == "__main__":
    result = asyncio.run(execute_workflow({"message": "test"}))
    print(f"Result: {result}")
`;

  return Array.from(imports).join('\n') + '\n' + code;
}

/**
 * 生成 TypeScript 代码
 */
export function generateTypeScriptCode(nodes: Node[], edges: Edge[]): string {
  let code = `/**
 * Generated Workflow Code
 * 
 * This code was automatically generated from a workflow.
 */

type Context = Record<string, any>;

`;

  // 为每个节点生成函数
  nodes.forEach((node) => {
    switch (node.type) {
      case 'start':
        code += `async function node_${node.id}_start(context: Context): Promise<any> {
  console.log("Starting workflow...");
  return context.initial_input || {};
}

`;
        break;

      case 'httpRequest':
        code += `async function node_${node.id}_httpRequest(context: Context): Promise<any> {
  const url = "${node.data.url || 'https://api.example.com'}";
  const method = "${node.data.method || 'GET'}";
  
  const response = await fetch(url, { method });
  return await response.json();
}

`;
        break;

      case 'textModel':
        code += `async function node_${node.id}_textModel(context: Context): Promise<any> {
  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer YOUR_API_KEY"
    },
    body: JSON.stringify({
      model: "${node.data.model || 'gpt-4'}",
      messages: [
        { role: "user", content: context.prompt || "" }
      ],
      temperature: ${node.data.temperature || 0.7},
      max_tokens: ${node.data.maxTokens || 2000}
    })
  });
  
  const data = await response.json();
  return data.choices[0].message.content;
}

`;
        break;

      case 'conditional':
        code += `async function node_${node.id}_conditional(context: Context): Promise<any> {
  const condition = ${node.data.condition || 'true'};
  return { result: condition, branch: condition ? "true" : "false" };
}

`;
        break;

      case 'javascript':
        code += `async function node_${node.id}_javascript(context: Context): Promise<any> {
  ${node.data.code || '// Your code here\n  return context.input1;'}
}

`;
        break;

      case 'prompt':
        code += `async function node_${node.id}_prompt(context: Context): Promise<any> {
  return \`${node.data.content || 'Enter your prompt...'}\`;
}

`;
        break;

      case 'end':
        code += `async function node_${node.id}_end(context: Context): Promise<any> {
  console.log("Workflow completed!");
  return context.final_result;
}

`;
        break;

      default:
        code += `async function node_${node.id}_${node.type}(context: Context): Promise<any> {
  // TODO: Implement ${node.type} logic
  return context.input;
}

`;
    }
  });

  // 生成主执行函数
  code += `async function executeWorkflow(initialInput: any): Promise<any> {
  const context: Context = { initial_input: initialInput };
  
`;

  // 按照边的顺序执行节点
  const startNode = nodes.find((n) => n.type === 'start');
  if (startNode) {
    code += `  // Execute nodes\n`;
    code += `  let result = await node_${startNode.id}_start(context);\n`;
    code += `  context.node_${startNode.id} = result;\n\n`;

    // 简单的顺序执行
    const otherNodes = nodes.filter((n) => n.type !== 'start' && n.type !== 'end');
    otherNodes.forEach((node) => {
      code += `  result = await node_${node.id}_${node.type}(context);\n`;
      code += `  context.node_${node.id} = result;\n\n`;
    });

    const endNode = nodes.find((n) => n.type === 'end');
    if (endNode) {
      code += `  const finalResult = await node_${endNode.id}_end(context);\n`;
      code += `  return finalResult;\n`;
    }
  }

  code += `}

// Execute the workflow
executeWorkflow({ message: "test" })
  .then(result => console.log("Result:", result))
  .catch(error => console.error("Error:", error));
`;

  return code;
}

