const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const { chromium } = require('playwright');

// Browser-only fixtures: no provider requests, credentials, or production data are used.
async function main() {
  const output = path.resolve(__dirname, '../logs/sunoapi-ui');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  let role = 'super_admin';
  let saved;
  const errors = [];
  const quota = { is_unlimited: true, remaining_tasks: null, used_tasks: 0 };
  let config = {
    active_implementation: 'official', active_model: 'v4.5',
    sunoapi_org_token_configured: false, sunoapi_org_token_hint: null,
    sunoapi_org_callback_base_url: null, sunoapi_org_callback_ready: false,
    updated_by_id: 1, updated_at: '2026-09-08T00:00:00Z',
  };
  await context.addInitScript(() => localStorage.setItem('blue_music_access_token', 'browser-test-only'));
  await context.route('**/api/v1/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const endpoint = url.pathname.replace('/api/v1', '');
    let body = { items: [], total: 0 };
    if (endpoint === '/auth/me') body = {
      id: 1, username: 'UI Test', role, is_active: true, agent_permissions: ['music'],
      music_quota: quota, watermark_text: 'UI Test',
    };
    if (endpoint === '/music/settings') {
      if (request.method() === 'PUT') {
        saved = request.postDataJSON();
        config = { ...config, active_implementation: saved.active_implementation,
          active_model: saved.active_model, sunoapi_org_token_configured: true,
          sunoapi_org_token_hint: '****test', sunoapi_org_callback_ready: true,
          sunoapi_org_callback_base_url: saved.sunoapi_org_callback_base_url };
      }
      body = role === 'super_admin' ? config : { ...config,
        sunoapi_org_token_hint: null, sunoapi_org_callback_base_url: null };
    }
    if (endpoint === '/music/provider-status') body = {
      provider: 'suno', implementation: config.active_implementation,
      configured: config.sunoapi_org_token_configured,
      integration_status: config.sunoapi_org_token_configured ? 'ready' : 'waiting_access',
      message: 'Browser test', platform_url: 'https://sunoapi.org/api-key',
      queue_mode: 'redis', max_concurrency: 1, min_request_interval_seconds: 30,
      active_model: config.active_model, user_quota: quota, quota: null,
    };
    if (endpoint === '/music/results') body = { total: 1, items: [{
      id: 1, task_id: 1, external_id: 'fixture-track', title: 'Test Song',
      media_type: 'audio/mpeg', duration_seconds: 150, image_url: null,
      provider_page_url: null, storage_backend: 'local', storage_error: null,
      audio_ready: true, audio_path: '/music/results/1/audio', download_path: '/music/results/1/download',
      task_operation: 'generate', task_model: 'v4.5', style_tags: ['pop'], negative_tags: [],
      created_at: '2026-09-08T00:00:00Z',
    }] };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(`${process.env.UI_TEST_BASE_URL || 'http://127.0.0.1:5173'}/music`);
    await page.getByRole('button', { name: '接口设置', exact: true }).click();
    await page.getByRole('combobox', { name: '接口实现' }).click();
    await page.getByText('sunoapi.org（第三方 Token 接入）', { exact: true }).click();
    await page.getByLabel('SunoAPI Token', { exact: true }).fill('ui-fixture-token-test');
    await page.getByLabel('回调公网地址', { exact: true }).fill('https://music.example.com');
    await page.getByRole('button', { name: '保存设置', exact: true }).click();
    await page.getByRole('dialog').waitFor({ state: 'hidden' });
    assert.equal(saved.sunoapi_org_token, 'ui-fixture-token-test');
    assert.equal(saved.active_implementation, 'sunoapi_org');
    assert.equal(await page.getByRole('button', { name: '续写', exact: true }).count(), 0);
    assert.equal(await page.getByRole('button', { name: '授权改编', exact: true }).count(), 0);
    await page.getByRole('button', { name: '接口设置', exact: true }).click();
    assert.equal(await page.getByLabel('SunoAPI Token', { exact: true }).inputValue(), '');
    await page.screenshot({ path: path.join(output, 'desktop-settings.png'), animations: 'disabled' });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForFunction(() => {
      const bounds = document.querySelector('[role="dialog"]').getBoundingClientRect();
      return bounds.x >= 0 && bounds.x + bounds.width <= window.innerWidth + 1;
    });
    await page.screenshot({ path: path.join(output, 'mobile-settings.png'), animations: 'disabled' });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
    const dialog = await page.getByRole('dialog').boundingBox();
    assert.ok(dialog.x >= 0 && dialog.x + dialog.width <= 391);
    await page.getByRole('button', { name: /^取\s*消$/ }).click();
    role = 'member';
    await page.reload();
    await page.getByText('Test Song', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: '接口设置', exact: true }).count(), 0);
    await page.screenshot({ path: path.join(output, 'mobile-member.png'), fullPage: true });
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: true, viewports: [1440, 390], output }));
  } catch (error) {
    console.error(await page.getByRole('dialog').evaluate(element => ({
      bounds: element.getBoundingClientRect().toJSON(),
      width: getComputedStyle(element).width, maxWidth: getComputedStyle(element).maxWidth,
      transform: getComputedStyle(element).transform,
    })).catch(() => null));
    await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true, animations: 'disabled' });
    throw error;
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
