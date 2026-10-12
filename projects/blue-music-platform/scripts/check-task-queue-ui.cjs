const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

async function main() {
  const output = path.resolve(__dirname, '../logs/task-queue-ui');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 1000 } });
      await context.addInitScript(() => localStorage.setItem('blue_music_access_token', 'queue-ui-fixture'));
      await context.route('**/api/v1/**', async route => {
        const endpoint = new URL(route.request().url()).pathname.replace('/api/v1', '');
        let body = { items: [], total: 0 };
        if (endpoint === '/auth/me') body = { id: 1, username: 'Queue fixture', role: 'super_admin', agent_permissions: [], is_active: true };
        if (endpoint === '/workflows/templates') body = [];
        if (endpoint === '/music/settings') body = { active_implementation: 'sunoapi_org', active_model: 'v4.5', sunoapi_org_token_configured: true, sunoapi_org_callback_ready: true };
        if (endpoint === '/music/provider-status') body = { provider: 'suno', implementation: 'sunoapi_org', configured: true, integration_status: 'ready', active_model: 'v4.5', queue_mode: 'redis', max_concurrency: 1, min_request_interval_seconds: 30, user_quota: { is_unlimited: true }, quota: null };
        if (endpoint === '/workflows/queue') body = {
          limit: 2, active_count: 2, items: [
            { kind: 'workflow', id: 101, title: '关于城市与远方的歌曲创作任务', status: 'pending', position: 2, expires_at: null },
            { kind: 'workflow', id: 102, title: '等待审核决定的歌词创作', status: 'paused', position: null, expires_at: '2026-10-14T12:00:00Z' },
          ],
        };
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
      });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      for (const route of ['music', 'workflows']) {
        await page.goto(`http://127.0.0.1:5173/${route}`);
        await page.getByText('我的任务队列', { exact: true }).waitFor();
        await page.getByText('排队第 2 位', { exact: true }).waitFor();
        assert.equal(await page.getByText('两个任务名额已满', { exact: true }).count(), 1);
        assert.equal(await page.getByText('待人工处理', { exact: true }).count(), 1);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
        assert.equal(overflow, false, `${route} overflow at ${width}`);
        await page.screenshot({ path: path.join(output, `${route}-${width}.png`), animations: 'disabled' });
      }
      assert.deepEqual(errors, []);
      await context.close();
    }
  } finally {
    await browser.close();
  }
  console.log('Queue UI verified at 1440/390px with isolated fixtures');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
