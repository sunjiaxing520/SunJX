const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

// Isolated browser fixtures: never submit credentials to the running backend.
async function main() {
  const output = path.resolve(__dirname, '../logs/provider-presets-ui');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const templates = ['bigmodel', 'gemini', 'openai_compatible'].map(key => ({
      key, display_name: key === 'gemini' ? 'Google Gemini' : key,
      protocol: 'openai_compatible', requires_api_key: true,
      default_base_url: key === 'openai_compatible' ? '' : 'https://example.com/v1',
      default_model: key === 'gemini' ? 'gemini-2.5-flash' : key === 'bigmodel' ? 'glm-test' : '',
      supports_json_mode: true, max_tokens_parameter: 'max_tokens',
    }));
    let saved;
    let creates = 0;
    let tests = 0;
    let activations = 0;
    let testStatus = 'failed';
    await context.addInitScript(() => localStorage.setItem('blue_music_access_token', 'ui-fixture'));
    await context.route('**/api/v1/**', async route => {
      const endpoint = new URL(route.request().url()).pathname;
      let body = {};
      if (endpoint.endsWith('/auth/me')) body = {
        id: 1, username: 'UI Test', role: 'super_admin', is_active: true,
        agent_permissions: [], watermark_text: 'UI Test',
      };
      if (endpoint.endsWith('/templates')) body = templates;
      if (endpoint.endsWith('/ai-providers')) {
        body = { items: [], runtime_source: 'environment', environment_fallback: { configured: false } };
        if (route.request().method() === 'POST') {
          creates += 1;
          saved = { ...route.request().postDataJSON(), id: creates, is_active: false };
          body = saved;
        }
      }
      if (endpoint.endsWith('/test')) {
        tests += 1;
        body = { status: testStatus, message: testStatus === 'failed' ? 'HTTP 401: Key invalid' : 'Connection verified',
          provider: saved, api_usage: { total_tokens: 16 } };
      }
      if (endpoint.endsWith('/activate')) {
        activations += 1;
        body = { ...saved, is_active: true };
      }
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:5173/admin/ai-providers');
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.getByRole('button', { name: '新建接口', exact: true }).click();
      const dialog = page.getByRole('dialog');
      await dialog.getByLabel('API Key', { exact: true }).fill('discard-me');
      await dialog.getByRole('combobox', { name: '接口模板' }).click();
      await page.getByText('Google Gemini', { exact: true }).click();
      assert.equal(await dialog.getByLabel('API Key', { exact: true }).inputValue(), '');
      assert.equal(await dialog.locator('details').getAttribute('open'), null);
      await dialog.getByLabel('API Key', { exact: true }).fill('fixture-only-key');
      // Hide the fixture key in the screenshot; never use a real key here.
      await page.screenshot({ path: path.join(output, `${width}-preset.png`), animations: 'disabled' });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await dialog.getByRole('button', { name: '仅保存', exact: true }).click();
      await dialog.waitFor({ state: 'hidden' });
      assert.equal(saved.template_key, 'gemini');
      assert.equal(saved.name, 'Google Gemini');
      assert.equal(saved.model, 'gemini-2.5-flash');
      assert.equal(saved.api_key, 'fixture-only-key');
    }
    await page.getByRole('button', { name: '新建接口', exact: true }).click();
    const dialog = page.getByRole('dialog');
    assert.equal(await dialog.getByLabel('API Key', { exact: true }).inputValue(), '');
    await dialog.getByRole('combobox', { name: '接口模板' }).click();
    await page.getByText('openai_compatible', { exact: true }).click();
    assert.notEqual(await dialog.locator('details').getAttribute('open'), null);
    assert.equal(await dialog.getByLabel('Base URL', { exact: true }).inputValue(), '');
    await dialog.getByRole('button', { name: /^取\s*消$/ }).click();
    for (const status of ['failed', 'success']) {
      testStatus = status;
      const before = creates;
      await page.getByRole('button', { name: '新建接口', exact: true }).click();
      await dialog.getByLabel('API Key', { exact: true }).fill('fixture-test-key');
      await dialog.getByRole('button', { name: '保存并测试', exact: true }).click();
      await dialog.waitFor({ state: 'hidden' });
      await page.getByRole('alert').filter({ hasText: status === 'failed' ? 'Key invalid' : 'Connection verified' }).waitFor();
      assert.equal(creates, before + 1);
      assert.equal(activations, 0);
      await page.screenshot({ path: path.join(output, `test-${status}.png`), animations: 'disabled' });
    }
    assert.equal(tests, 2);
    await page.getByRole('button', { name: '启用此接口', exact: true }).click();
    await page.getByRole('button', { name: /^启\s*用$/ }).click();
    await page.getByRole('button', { name: '启用此接口', exact: true }).waitFor({ state: 'hidden' });
    assert.equal(activations, 1);
    assert.deepEqual(errors, []);
    console.log('PASS: key-only presets, secret clearing, custom fields, desktop/mobile screenshots');
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
