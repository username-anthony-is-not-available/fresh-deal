// src/config/colors.ts

export const lightTheme = {
  background: '#f5f5f5',
  surface: '#ffffff',
  primary: '#22c55e',
  text: '#111827',
  textSecondary: '#6b7280',
  border: '#e5e7eb',
  accent: '#f97316',
  error: '#ef4444',
  success: '#10b981',
};

export const darkTheme = {
  background: '#111827',
  surface: '#1f2937',
  primary: '#22c55e',
  text: '#f9fafb',
  textSecondary: '#9ca3af',
  border: '#374151',
  accent: '#fb923c',
  error: '#f87171',
  success: '#34d399',
};

export type ThemeColors = typeof lightTheme;
