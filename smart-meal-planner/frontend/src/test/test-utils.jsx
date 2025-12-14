import React from 'react';
import { render } from '@testing-library/react';
import { AuthProvider } from '../src/context/AuthContext.jsx';
import i18n from '../src/i18n.js';
import { I18nextProvider } from 'react-i18next';

const AllTheProviders = ({ children }) => {
  return (
    <AuthProvider>
      <I18nextProvider i18n={i18n}>
        {children}
      </I18nextProvider>
    </AuthProvider>
  );
};

const customRender = (ui, options) =>
  render(ui, { wrapper: AllTheProviders, ...options });

// re-export everything
export * from '@testing-library/react';

// override render method
export { customRender as render };
