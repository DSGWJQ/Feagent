import { generateText, embed, generateObject } from 'ai';
import { google } from '@ai-sdk/google';
import { openai } from '@ai-sdk/openai';
import { z } from 'zod';

export const maxDuration = 60;

export async function POST(req: Request) {
  try {
    const { input } = await req.json();

    // HTTP Request
    const apiResponse = await fetch('https://v0-generated-agent-builder.vercel.app/api/demo-country', {
      method: 'GET',
    });
    const apiData = await apiResponse.json();

    // Text Generation
    const result = await generateText({
      model: 'openai/gpt-5-mini',
      prompt: input,
      temperature: 0.7,
      maxTokens: 300,
    });

    // Image Generation
    const imageResult = await generateText({
      model: google('gemini-2.5-flash-image'),
      prompt: input,
    });
    const images = imageResult.files?.filter(f => f.mediaType.startsWith('image/')).map(f => f.base64) || [];

    return Response.json({
      text: result.text,
      images,
      apiData,
      success: true
    });
  } catch (error) {
    console.error('Workflow error:', error);
    return Response.json({ error: 'Workflow execution failed' }, { status: 500 });
  }
}
