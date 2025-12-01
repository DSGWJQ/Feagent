/**
 * KnowledgeUploadPage - 知识库上传页面
 *
 * 提供一个独立的界面，让用户上传文档到知识库。
 * 复用 hooks/useKnowledge 中的逻辑，保证真实环境可用。
 */

import { useState } from 'react';
import { Card, Input, Typography, Space } from 'antd';
import type { InputProps } from 'antd';
import KnowledgeUpload from '@/components/KnowledgeUpload.example';

const { Title, Paragraph, Text } = Typography;

export const KnowledgeUploadPage: React.FC = () => {
  const [workflowId, setWorkflowId] = useState<string>('');

  const inputProps: InputProps = {
    placeholder: '不填写则作为全局知识库',
    value: workflowId,
    onChange: (event) => setWorkflowId(event.target.value),
    allowClear: true,
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)',
        padding: '48px 16px',
      }}
    >
      <Card
        style={{
          maxWidth: 960,
          margin: '0 auto',
          borderRadius: 20,
          boxShadow: '0 20px 60px rgba(15, 12, 41, 0.35)',
        }}
        styles={{ body: { padding: '32px 40px' } }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2} style={{ marginBottom: 12 }}>
              上传知识库
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              将 PDF、Word、Markdown 等文本上传到知识库，后续即可在工作流对话中引用这些资料。
            </Paragraph>
          </div>

          <div>
            <Text strong>关联工作流（可选）</Text>
            <Paragraph type="secondary" style={{ marginBottom: 8 }}>
              输入 workflow_id 可将文档存入指定工作流的私有知识库；留空则存入全局知识库。
            </Paragraph>
            <Input {...inputProps} />
          </div>

          <KnowledgeUpload workflowId={workflowId.trim() || undefined} />
        </Space>
      </Card>
    </div>
  );
};

export default KnowledgeUploadPage;
