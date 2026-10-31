import { defineConfig } from 'astro/config';

export default defineConfig({
  site: process.env.SITE_URL || 'https://digaopu1027-afk.github.io',
  base: process.env.BASE_PATH || '/',
  trailingSlash: 'always',
  output: 'static',
  devToolbar: { enabled: false },
});
