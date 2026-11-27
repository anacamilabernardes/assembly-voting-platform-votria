import { defineConfig } from '@playwright/test';

const python = process.env.PYTHON ?? 'python';
const db = '../backend/e2e.sqlite3';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:8000',
    locale: 'pt-BR',
    channel: process.env.PW_CHANNEL || undefined,
    trace: 'retain-on-failure',
  },
  webServer: {
    command:
      `rm -f ${db} && cd ../backend && DJANGO_SQLITE_PATH=e2e.sqlite3 ${python} manage.py migrate --noinput -v 0 && ` +
      `DJANGO_SQLITE_PATH=e2e.sqlite3 ${python} manage.py seed_demo && ` +
      `DJANGO_SQLITE_PATH=e2e.sqlite3 ${python} manage.py runserver 127.0.0.1:8000 --noreload`,
    url: 'http://127.0.0.1:8000/health/ready',
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
