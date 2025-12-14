/**
 * ThemeContext - 主题管理Context
 *
 * 提供主题状态管理和切换功能
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import type { ThemeMode } from '../styles/themes';
import { applyTheme, getStoredTheme, storeTheme } from '../styles/themes';

interface ThemeContextValue {
  theme: ThemeMode;
  toggleTheme: () => void;
  setTheme: (theme: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

interface ThemeProviderProps {
  children: React.ReactNode;
}

/**
 * ThemeProvider组件
 *
 * 管理全局主题状态，从localStorage读取初始值
 * 提供主题切换功能
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<ThemeMode>(() => {
    // 初始化时从localStorage读取
    return getStoredTheme();
  });

  // 初始化时应用主题
  useEffect(() => {
    applyTheme(theme);
  }, []);

  // 主题切换时应用并保存
  useEffect(() => {
    applyTheme(theme);
    storeTheme(theme);
  }, [theme]);

  const toggleTheme = () => {
    setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const setTheme = (newTheme: ThemeMode) => {
    setThemeState(newTheme);
  };

  const value: ThemeContextValue = {
    theme,
    toggleTheme,
    setTheme,
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/**
 * useTheme Hook
 *
 * 获取当前主题状态和切换函数
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { theme, toggleTheme } = useTheme();
 *   return <button onClick={toggleTheme}>Current: {theme}</button>;
 * }
 * ```
 */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}
