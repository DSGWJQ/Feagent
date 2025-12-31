import { Typography } from 'antd';

export type ResearchResult = {
  question: string;
  claims: unknown[];
  [key: string]: unknown;
};

export function ResearchResultDisplay({ result }: { result: ResearchResult }) {
  return (
    <div>
      <Typography.Title level={4}>{result.question}</Typography.Title>
      <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(result, null, 2)}</pre>
    </div>
  );
}
