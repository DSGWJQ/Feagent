import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import QueryProvider from './providers/QueryProvider';
import { theme } from '@/shared/styles/theme';
import '@/shared/styles/global.css';

function App() {
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <QueryProvider>
        <div style={{ padding: '50px', textAlign: 'center' }}>
          <h1>🎉 Agent 中台系统</h1>
          <p>前端项目骨架初始化成功！</p>
          <p style={{ marginTop: '20px', color: '#666' }}>
            技术栈：Vite + React + TypeScript + Ant Design Pro Components
          </p>
        </div>
      </QueryProvider>
    </ConfigProvider>
  );
}

export default App;

