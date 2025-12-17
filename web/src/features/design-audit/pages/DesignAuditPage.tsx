import React, { useState, useEffect } from 'react';
import { NeoButton } from '@/shared/components/common/NeoButton';
import { NeoCard } from '@/shared/components/common/NeoCard';
import { DeviceFrame } from '@/shared/components/common/DeviceFrame';
import styles from '../styles/design-audit.module.css';

// Import CSS Tokens
import '@/shared/styles/design-tokens.css';

export const DesignAuditPage: React.FC = () => {
    const [theme, setTheme] = useState<'light' | 'dark'>('light');

    // Theme Toggle Effect
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
    }, [theme]);

    const toggleTheme = () => {
        setTheme(prev => prev === 'light' ? 'dark' : 'light');
    };

    return (
        <div className={styles.container}>
            <header className={styles.header}>
                <h1 className={styles.title}>Visual System Master</h1>
                <div className={styles.controls}>
                    <NeoButton variant="secondary" onClick={toggleTheme}>
                        Theme: {theme.toUpperCase()}
                    </NeoButton>
                    <NeoButton variant="primary">
                        Export Config
                    </NeoButton>
                </div>
            </header>

            <div className={styles.grid}>
                <main className={styles.panel}>
                    <div className={styles.panelHeader}>
                        <div className={styles.panelTitle}>Design System 2.0</div>
                    </div>

                    {/* Section 1: Typography */}
                    <section className={styles.section}>
                        <h2 className={styles.sectionTitle}>Fluid Typography</h2>
                        <div className={styles.sectionBody}>
                            A strictly defined, fluid type scale derived from musical intervals. Designed for optimal readability (45-75 chars/line) and dramatic contrast.
                        </div>

                        <div className={styles.typeRow}>
                            <div className={styles.typeMeta}>Display D1<br />Inter 800</div>
                            <div style={{
                                fontSize: 'var(--font-d1-size)',
                                fontWeight: 'var(--font-d1-weight)',
                                lineHeight: 'var(--font-d1-line-height)',
                                letterSpacing: 'var(--font-d1-tracking)'
                            }}>
                                Visual Impact
                            </div>
                        </div>

                        <div className={styles.typeRow}>
                            <div className={styles.typeMeta}>Heading H1<br />Inter 600</div>
                            <div style={{
                                fontSize: 'var(--font-h1-size)',
                                fontWeight: 'var(--font-h1-weight)',
                                lineHeight: 'var(--font-h1-line-height)',
                                letterSpacing: 'var(--font-h1-tracking)'
                            }}>
                                Information Hierarchy
                            </div>
                        </div>

                        <div className={styles.typeRow}>
                            <div className={styles.typeMeta}>Body<br />Inter 400</div>
                            <div style={{
                                fontSize: 'var(--font-body-size)',
                                lineHeight: 'var(--font-body-line-height)'
                            }}>
                                The quick brown fox jumps over the lazy dog. Good design is as little design as possible. Less, but better.
                            </div>
                        </div>

                        <div className={styles.typeRow}>
                            <div className={styles.typeMeta}>Caption<br />Inter 500</div>
                            <div style={{
                                fontSize: 'var(--font-caption-size)',
                                fontWeight: 'var(--font-caption-weight)',
                                letterSpacing: 'var(--font-caption-tracking)'
                            }}>
                                METADATA / LABELS / UTILITY
                            </div>
                        </div>
                    </section>

                    {/* Section 2: Interactive Elements */}
                    <section className={styles.section}>
                        <h2 className={styles.sectionTitle}>Actionable Signals</h2>
                        <div className={styles.sectionBody}>
                            Interactive elements must communicate affordance clearly. We use high-contrast primary actions and subtle secondary states.
                        </div>

                        <div className={styles.componentRow}>
                            <NeoButton variant="primary">Primary Action</NeoButton>
                            <NeoButton variant="secondary">Secondary</NeoButton>
                            <NeoButton variant="ghost">Ghost Button</NeoButton>
                            <NeoButton disabled>Disabled</NeoButton>
                        </div>
                    </section>

                    {/* Section 3: Semantic Colors */}
                    <section className={styles.section}>
                        <h2 className={styles.sectionTitle}>Palette & Depth</h2>
                        <div className={styles.sectionBody}>
                            The "Stone" neutral scale provides warmth, while "Teal" and "Red" act as functional signals. Glassmorphism is used for layered context.
                        </div>
                        <div className={styles.colorGrid}>
                            <div className={styles.colorChip} style={{ background: 'var(--color-bg-canvas)', border: '1px solid var(--color-border-subtle)' }}>
                                <span className={styles.colorName} style={{ color: 'var(--color-text-primary)' }}>Canvas</span>
                            </div>
                            <div className={styles.colorChip} style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)' }}>
                                <span className={styles.checkMark}>WCAG AA</span>
                                <span className={styles.colorName} style={{ color: 'var(--color-text-primary)' }}>Surface</span>
                            </div>
                            <div className={styles.colorChip} style={{ background: 'var(--color-brand-accent)' }}>
                                <span className={styles.colorName} style={{ color: '#fff' }}>Brand Teal</span>
                            </div>
                            <div className={styles.colorChip} style={{ background: 'var(--color-action-primary-bg)' }}>
                                <span className={styles.colorName} style={{ color: 'var(--color-action-primary-text)' }}>Action Primary</span>
                            </div>
                        </div>
                    </section>

                    {/* Section 4: Mobile Simulation */}
                    <section className={styles.section}>
                        <h2 className={styles.sectionTitle}>Mobile-First Reality</h2>
                        <div className={styles.sectionBody}>
                            All designs must verify elegantly on mobile constraints.
                        </div>

                        <div className={styles.mobilePeviewContainer}>
                            <div className={styles.mobilePreviewText}>
                                <h3 style={{ fontSize: 'var(--font-h1-size)', marginBottom: '1rem' }}>Device Confirmation</h3>
                                <p style={{ lineHeight: 1.6, color: 'var(--color-text-secondary)', marginBottom: '2rem' }}>
                                    The <strong>DeviceFrame</strong> component simulates a physical viewport environment.
                                    This forces discipline in spacing and content density. Note the internal scrolling behavior.
                                </p>
                                <NeoButton variant="secondary">Open Full Mobile View</NeoButton>
                            </div>

                            <DeviceFrame>
                                <div style={{ padding: '24px 20px' }}>
                                    <h4 style={{
                                        fontSize: 'var(--font-h1-size)',
                                        marginBottom: '16px',
                                        lineHeight: 1.2
                                    }}>Mobile View</h4>
                                    <p style={{
                                        fontSize: '0.95rem',
                                        lineHeight: 1.6,
                                        color: 'var(--color-text-secondary)',
                                        marginBottom: '24px'
                                    }}>
                                        Content flows naturally here. Typography scales down slightly but maintains hierarchy.
                                    </p>

                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                        <NeoCard title="Mobile Card" variant="raised">
                                            Compact information display.
                                        </NeoCard>
                                        <NeoCard title="Another Item">
                                            Secondary content.
                                        </NeoCard>
                                        <NeoButton variant="primary" style={{ width: '100%', marginTop: '12px' }}>
                                            Full Width Action
                                        </NeoButton>
                                    </div>

                                    {/* Long content to test scroll */}
                                    <div style={{ marginTop: '32px', opacity: 0.5 }}>
                                        {[1, 2, 3].map(i => (
                                            <p key={i} style={{ fontSize: '0.85rem', marginBottom: '12px' }}>
                                                Scroll content simulation line {i}...
                                            </p>
                                        ))}
                                    </div>
                                </div>
                            </DeviceFrame>
                        </div>
                    </section>

                </main>
            </div>
        </div>
    );
};

export default DesignAuditPage;
