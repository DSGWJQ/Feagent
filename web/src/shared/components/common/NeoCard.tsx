import React from 'react';
import classNames from 'classnames';
import styles from './NeoCard.module.css';
import '@/shared/styles/design-tokens.css'; // Ensure tokens are loaded


export interface NeoCardProps {
    /** 标题 */
    title?: React.ReactNode;
    /** 描述/副标题 */
    description?: React.ReactNode;
    /** 内容 */
    children: React.ReactNode;
    /**
     * 变体
     * - standard: 标准石板（默认）
     * - raised: 浮起效果（适合可点击卡片）
     * - flat: 扁平日耳曼式（无阴影，仅边框）
     */
    variant?: 'standard' | 'raised' | 'flat';
    /** 是否应用 neoStone 纹理（默认为 true） */
    stoneTexture?: boolean;
    /** 自定义类名 */
    className?: string;
    /** 右侧额外操作区 */
    extra?: React.ReactNode;
    /** 点击事件 */
    onClick?: () => void;
    /** 样式覆盖 */
    style?: React.CSSProperties;
}

/**
 * NeoCard - 新古典主义卡片
 *
 * 代表一块经过切割和打磨的石板。
 * 可用于展示信息、作为容器或交互单元。
 */
export function NeoCard({
    title,
    description,
    children,
    variant = 'standard',
    stoneTexture = true,
    className,
    extra,
    onClick,
    style
}: NeoCardProps) {
    const cardClass = classNames(
        styles.card,
        {
            'neoStone': stoneTexture, // Apply global stone texture
            [styles.variantRaised]: variant === 'raised' || (variant === 'standard' && onClick),
            [styles.variantFlat]: variant === 'flat',
        },
        className
    );

    return (
        <div className={cardClass} onClick={onClick} style={style}>
            {(title || description || extra) && (
                <div className={styles.header}>
                    <div style={{ flex: 1 }}>
                        {title && <h3 className={styles.title}>{title}</h3>}
                        {description && <div className={styles.description}>{description}</div>}
                    </div>
                    {extra && <div className={styles.extra}>{extra}</div>}
                </div>
            )}
            <div className={styles.content}>
                {children}
            </div>
        </div>
    );
}
