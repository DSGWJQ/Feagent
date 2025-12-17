
import React from 'react';
import styles from '../styles/sim-replica.module.css';
import {
    SlackOutlined,
    MailOutlined,
    GoogleOutlined,
    ArrowRightOutlined
} from '@ant-design/icons';

// Simple SVG Icons
const Icons = {
    Calendar: () => (
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2" /><line x1="16" x2="16" y1="2" y2="6" /><line x1="8" x2="8" y1="2" y2="6" /><line x1="3" x2="21" y1="10" y2="10" /></svg>
    ),
    Bot: () => (
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 8V4H8" /><rect width="16" height="12" x="4" y="8" rx="2" /><path d="M2 14h2" /><path d="M20 14h2" /><path d="M15 13v2" /><path d="M9 13v2" /></svg>
    )
};

export const SimReplicaPage: React.FC = () => {
    return (
        <div className={styles.container}>
            {/* Navbar */}
            <nav className={styles.navbar}>
                <div className={styles.navLeft}>
                    <div className={styles.logo}>sim</div>
                    <div className={styles.navLinks}>
                        <a href="#" className={styles.navLink}>Docs</a>
                        <a href="#" className={styles.navLink}>Pricing</a>
                        <a href="#" className={styles.navLink}>Enterprise</a>
                        <a href="#" className={styles.navLink}>Careers</a>
                        <a href="#" className={styles.navLink}>Github 22.1k</a>
                    </div>
                </div>
                <div className={styles.navRight}>
                    <a href="#" className={styles.loginLink}>Log in &gt;</a>
                    <button className={styles.getStartedBtn}>Get started &gt;</button>
                </div>
            </nav>

            {/* Hero Section */}
            <header className={styles.hero}>
                <h1 className={styles.heroTitle}>Workflows for LLMs</h1>
                <p className={styles.heroSubtitle}>Build and deploy AI agent workflows</p>

                {/* Integration Icons - Using approximate Antd Icons or simplified visuals */}
                <div className={styles.integrations}>
                    <div className={styles.integrationIcon} style={{ color: '#E01E5A' }}><SlackOutlined style={{ fontSize: 24 }} /></div>
                    <div className={styles.integrationIcon} style={{ color: '#EA4335' }}><GoogleOutlined style={{ fontSize: 24 }} /></div>
                    <div className={styles.integrationIcon} style={{ color: '#0078D4' }}><MailOutlined style={{ fontSize: 24 }} /></div>
                    <div className={styles.integrationIcon} style={{ color: '#0052CC' }}><div style={{ fontWeight: 'bold', fontSize: 14 }}>Jira</div></div>
                    {/* Placeholder circles for others to maintain the look */}
                    <div className={styles.integrationIcon} style={{ background: '#f8f9fa' }}>⚡</div>
                    <div className={styles.integrationIcon} style={{ background: '#f8f9fa' }}>L</div>
                    <div className={styles.integrationIcon} style={{ color: '#5865F2' }}>D</div>
                    <div className={styles.integrationIcon} style={{ color: '#4285F4' }}>📅</div>
                    <div className={styles.integrationIcon} style={{ color: '#635BFF' }}>S</div>
                    <div className={styles.integrationIcon} style={{ color: '#000000' }}>N</div>
                    <div className={styles.integrationIcon} style={{ color: '#0F9D58' }}>📊</div>
                    <div className={styles.integrationIcon} style={{ color: '#FFD700' }}>📁</div>
                </div>

                {/* Search Bar */}
                <div className={styles.searchBarContainer}>
                    <input
                        className={styles.searchInput}
                        placeholder="Ask Sim to build an agent to read my emails..."
                    />
                    <button className={styles.arrowButton}>
                        <ArrowRightOutlined />
                    </button>
                </div>
            </header>

            {/* Workflow Visualization Area */}
            <div className={styles.workflowArea}>
                <div className={styles.gridBackground}>
                    {/* SVG Canvas for lines can go here */}
                    <svg width="100%" height="100%" style={{ position: 'absolute', top: 0, left: 0 }}>
                        <defs>
                            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                                <circle cx="1" cy="1" r="1" fill="#e5e7eb" />
                            </pattern>
                        </defs>
                        <rect width="100%" height="100%" fill="url(#grid)" />

                        {/* Connecting Lines - simplified svg paths */}
                        <path d="M 200 450 L 300 450 L 300 300 L 800 300" fill="none" stroke="#e5e7eb" strokeWidth="2" strokeDasharray="5,5" />
                    </svg>
                </div>

                {/* Schedule Node */}
                <div className={`${styles.nodeCard} ${styles.scheduleNode} `}>
                    <div className={styles.nodeTitle}>
                        <Icons.Calendar /> Schedule
                    </div>
                    <div className={styles.nodeContent}>
                        09:00AM Daily &nbsp; PST
                    </div>
                </div>

                {/* Loop Region */}
                <div className={styles.loopRegion}>
                    <div className={styles.loopLabel}>Loop</div>

                    {/* Agent Node in Loop */}
                    <div className={`${styles.nodeCard} ${styles.agentNode} `}>
                        <div className={styles.nodeTitle}>
                            <Icons.Bot /> Agent
                        </div>
                        <div className={styles.nodeContent}>
                            gpt-5 &nbsp; You are a support ag...
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
