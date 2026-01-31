import React from 'react';
import classNames from 'classnames';
import styles from './PageShell.module.css';

export interface PageShellProps {
    /** 页面标题 */
    title: React.ReactNode;
    /** 页面描述/副标题 */
    description?: React.ReactNode;
    /** 右上角操作区 */
    actions?: React.ReactNode;
    /** 页面内容 */
    children: React.ReactNode;
    /**
     * 变体风格
     * - default: 标准透明背景，适合内部已有 Card 的页面
     * - stone: 整个页面呈石质背景（暂未实装特殊效果，预留）
     */
    variant?: 'default' | 'stone';
    /** 自定义类名 */
    className?: string;
}

/**
 * PageShell - 标准页面壳组件
 *
 * 提供统一的标题区（Lintel 风格）和内容容器。
 * 遵循新古典主义 "Order & Structure" 原则。
 */
export function PageShell({
    title,
    description,
    actions,
    children,
    variant = 'default',
    className
}: PageShellProps) {
    const containerClass = classNames(
        styles.container,
        styles[`variant${variant.charAt(0).toUpperCase() + variant.slice(1)}`],
        'neoReveal', // 入场动画
        className
    );

    return (
        <div className={containerClass}>
            <div className={styles.header}>
                <div className={styles.titleRow}>
                    <div className={styles.titleWrapper}>
                        <h1 className={styles.title}>{title}</h1>
                        {description && (
                            <div className={styles.description}>{description}</div>
                        )}
                    </div>

                    {actions && (
                        <div className={styles.actions}>
                            {actions}
                        </div>
                    )}
                </div>
            </div>

            <div className={styles.content}>
                {children}
            </div>
        </div>
    );
}
