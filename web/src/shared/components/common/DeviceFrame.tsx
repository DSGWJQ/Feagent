import React from 'react';

interface DeviceFrameProps {
    children: React.ReactNode;
    width?: number;
    height?: number;
    className?: string;
}

/**
 * DeviceFrame
 *
 * A component that visually simulates a mobile device.
 * Used for testing ease and presenting mobile-first designs in a desktop environment.
 *
 * 1. Simulates a generic modern smartphone (approx 390x844).
 * 2. Enforces independent scrolling context (overflow: auto).
 * 3. Adds visual flair (bevels, shadows, notch hint).
 */
export const DeviceFrame: React.FC<DeviceFrameProps> = ({
    children,
    width = 390,
    height = 844,
    className
}) => {
    return (
        <div
            className={className}
            style={{
                width: width + 24, // + borders
                height: height + 24,
                margin: '0 auto',
                position: 'relative',
                background: '#1a1a1a', // Frame color
                borderRadius: '40px',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5), inset 0 0 0 2px #333',
                padding: '12px',
                boxSizing: 'border-box',
                display: 'flex',
                flexDirection: 'column'
            }}
        >
            {/* Notch / Speaker Hint */}
            <div style={{
                position: 'absolute',
                top: '20px',
                left: '50%',
                transform: 'translateX(-50%)',
                width: '100px',
                height: '24px',
                background: '#000',
                borderRadius: '12px',
                zIndex: 100,
                pointerEvents: 'none'
            }} />

            {/* Screen Container */}
            <div style={{
                width: '100%',
                height: '100%',
                background: 'var(--color-bg-canvas)',
                borderRadius: '32px',
                overflow: 'hidden',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column'
            }}>
                {/* Scrollable Content Area */}
                <div style={{
                    flex: 1,
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    position: 'relative',
                    // Hide scrollbar for aesthetics but allow scroll
                    scrollbarWidth: 'none',
                    msOverflowStyle: 'none'
                }}>
                    {/* Inner wrapper to match user content expectations */}
                    {children}
                </div>
            </div>
        </div>
    );
};
