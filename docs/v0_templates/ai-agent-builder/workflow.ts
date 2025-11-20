import { generateText, embed, generateObject, tool } from 'ai';
import { google } from '@ai-sdk/google';
import { openai } from '@ai-sdk/openai';
import { z } from 'zod';

export async function runAgentWorkflow(initialInput?: string) {
  // Start Node
  const node_1 = initialInput || '';

  // HTTP Request Node
  const node_2_response = await fetch('https://v0-generated-agent-builder.vercel.app/api/demo-country', {
    method: 'GET',
  });
  const node_2 = await node_2_response.json();

  // Conditional Node
  const node_3 = (() => {
    const input1 = node_2;
    return input1.country === 'US';
  })();

  if (node_3) {
    // True branch
  } else {
    // False branch
  }

  // Prompt Node
  const node_4 = `Write a short patriotic poem about the United States`;

  // Text Model Node
  const node_6_result = await generateText({
    model: 'openai/gpt-5-mini',
    prompt: node_4,
    temperature: 0.7,
    maxTokens: 300,
  });
  const node_6 = node_6_result.text;

  // Prompt Node
  const node_5 = `Write a welcoming message for visitors from ${node_3}`;

  // Text Model Node
  const node_7_result = await generateText({
    model: 'openai/gpt-5-mini',
    prompt: node_5,
    temperature: 0.7,
    maxTokens: 300,
  });
  const node_7 = node_7_result.text;

  // Prompt Node
  const node_8 = `Generate an artistic image representing this text: ${node_6}`;

  // Image Generation Node
  const node_9_result = await generateText({
    model: google('gemini-2.5-flash-image'),
    prompt: node_8,
  });
  // Extract images from files
  const node_9 = node_9_result.files?.filter(f => f.mediaType.startsWith('image/')).map(f => f.base64) || [];

  // End Node
  const node_10 = node_9;
  return node_10;

}
