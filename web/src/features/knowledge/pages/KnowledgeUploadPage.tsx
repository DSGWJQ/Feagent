/**
 * KnowledgeUploadPage - 知识库上传页面
 *
 * 提供一个独立的界面，让用户上传文档到知识库。
 * 复用 hooks/useKnowledge 中的逻辑，保证真实环境可用。
 */

import { useState } from 'react';
import { Input, Typography } from 'antd';
import type { InputProps } from 'antd';
import KnowledgeUpload from '@/components/KnowledgeUpload.example';
import { PageShell } from '@/shared/components/layout/PageShell';
import { NeoCard } from '@/shared/components/common/NeoCard';
import styles from '../styles/knowledge.module.css';

const { Paragraph, Text } = Typography;

export const KnowledgeUploadPage: React.FC = () => {
  const [workflowId, setWorkflowId] = useState<string>('');

  const inputProps: InputProps = {
    placeholder: '不填写则作为全局知识库',
    value: workflowId,
    onChange: (event) => setWorkflowId(event.target.value),
    allowClear: true,
  };

  return (
    <PageShell
      title="Knowledge Archives"
      description="Digitize and index documents for the eternal repository."
    >
      <div className={styles.container}>
        {/* Workflow Association */}
        <NeoCard
          title="Archive Designation"
          description="Specify the target workflow for this knowledge ingestion."
          variant="flat"
        >
          <Text strong style={{ display: 'block', marginBottom: '8px', color: 'var(--neo-text)' }}>
            Workflow Reference ID (Optional)
          </Text>
          <Input
            {...inputProps}
            style={{ fontFamily: 'var(--font-family-mono)' }}
            prefix={<span style={{ color: 'var(--neo-text-3)' }}>REF:</span>}
          />
          <Paragraph type="secondary" style={{ marginTop: '8px', fontSize: '12px' }}>
            Leave blank to index into the Global Library.
          </Paragraph>
        </NeoCard>

        {/* Upload Area */}
        <NeoCard
          title="Acquisition Station"
          variant="raised"
        >
          <KnowledgeUpload
            workflowId={workflowId.trim() || undefined}
            className={styles.dropZoneWrapper}
          />
        </NeoCard>
      </div>
    </PageShell>
  );
};

export default KnowledgeUploadPage;
