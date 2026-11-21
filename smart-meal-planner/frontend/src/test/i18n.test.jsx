import { describe, it, expect, vi } from 'vitest';

// The real HttpApi backend fetches /locales/... over HTTP, which never
// resolves in jsdom and hangs the worker; stub it (and the detector) so
// init completes synchronously with an empty resource bundle.
vi.mock('i18next-http-backend', () => ({
  default: class {
    static type = 'backend';
    type = 'backend';
    init() {}
    read(_lng, _ns, callback) { callback(null, {}); }
  },
}));
vi.mock('i18next-browser-languagedetector', () => ({
  default: class {
    static type = 'languageDetector';
    type = 'languageDetector';
    init() {}
    detect() { return 'en'; }
    cacheUserLanguage() {}
  },
}));

import i18n from '../i18n';

describe('i18n', () => {
  it('initializes with English as the fallback language', async () => {
    await new Promise((resolve) => {
      if (i18n.isInitialized) resolve();
      else {
        i18n.on('initialized', resolve);
        setTimeout(resolve, 2000);
      }
    });
    expect(i18n.isInitialized).toBe(true);
    expect(i18n.language).toBe('en');
    expect(i18n.options.supportedLngs).toContain('en');
    expect(i18n.options.supportedLngs).toContain('fr');
  });
});
