const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

// Synthetic PCM silence for playback checks; no copyrighted/customer music.
const wav = Buffer.alloc(44 + 16000 * 2 * 30);
wav.write('RIFF'); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8);
wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
wav.writeUInt32LE(16000, 24); wav.writeUInt32LE(32000, 28); wav.writeUInt16LE(2, 32);
wav.writeUInt16LE(16, 34); wav.write('data', 36); wav.writeUInt32LE(wav.length - 44, 40);

async function main() {
  const output = path.resolve(__dirname, '../logs/task-queue-ui');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 1000 } });
      const group = { task_id: 77, title: '城市夜归人', display_label: null, note: null, is_marked: false,
        lyrics: '[Verse 1]\n城市的灯照亮远方', instrumental: false, lyrics_task_id: 31, lyrics_version_id: 42,
        created_at: '2026-10-18T08:00:00Z', model: 'v4.5', results: [1, 2].map(id => ({
          id, task_id: 77, external_id: `fixture-${id}`, title: `城市夜归人 ${id}`, media_type: 'audio/mpeg',
          duration_seconds: 150, image_url: null, audio_ready: true, audio_path: `/music/results/${id}/audio`,
          download_path: `/music/results/${id}/download`, storage_backend: 'local', storage_error: null,
          task_operation: 'generate', task_model: 'v4.5', style_tags: ['流行'], negative_tags: [],
          created_at: '2026-10-18T08:00:00Z', provider_page_url: null,
        })) };
      await context.addInitScript(() => localStorage.setItem('blue_music_access_token', 'queue-ui-fixture'));
      await context.route('**/api/v1/**', async route => {
        const endpoint = new URL(route.request().url()).pathname.replace('/api/v1', '');
        if (/\/music\/results\/\d+\/audio$/.test(endpoint)) {
          await route.fulfill({ contentType: 'audio/wav', body: wav }); return;
        }
        let body = { items: [], total: 0 };
        if (endpoint === '/auth/me') body = { id: 1, username: 'Queue fixture', role: 'super_admin', agent_permissions: ['music'], is_active: true, music_quota: { is_unlimited: true, remaining_tasks: null, used_tasks: 0 }, watermark_text: 'UI fixture' };
        if (endpoint === '/workflows/templates' || endpoint === '/review-agents') body = [];
        if (endpoint === '/music/result-groups') body = { items: [group], total: 1 };
        if (endpoint === '/music/result-groups/77') { Object.assign(group, route.request().postDataJSON()); body = group; }
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
      page.on('console', message => { if (message.type() === 'error') console.error(message.text()); });
      for (const route of ['music', 'workflows']) {
        await page.goto(`http://127.0.0.1:5173/${route}`);
        await page.getByText('我的任务队列', { exact: true }).waitFor().catch(async error => {
          console.error({ errors, url: page.url(), body: (await page.locator('body').innerText()).slice(0, 2000) });
          throw error;
        });
        await page.getByText('排队第 2 位', { exact: true }).waitFor();
        assert.equal(await page.getByText('两个任务名额已满', { exact: true }).count(), 1);
        assert.equal(await page.getByText('待人工处理', { exact: true }).count(), 1);
        if (route === 'music') {
          assert.equal(await page.getByText('版本 A', { exact: true }).count(), 0);
          await page.locator('.music-group-open').click();
          await page.getByText('版本 A', { exact: true }).waitFor();
          await page.getByText('版本 B', { exact: true }).waitFor();
          await page.getByRole('button', { name: '查看歌词', exact: true }).click();
          await page.getByText('生成时使用的歌词', { exact: true }).waitFor();
          assert.equal(await page.locator('.music-group-lyrics pre').innerText(), group.lyrics);
          assert.equal(await page.getByRole('link', { name: '歌词记录 #31 · 版本 #42' }).getAttribute('href'), '/lyrics?task_id=31&version_id=42');
          await page.getByRole('button', { name: '标记分组', exact: true }).click();
          await page.getByRole('button', { name: '取消分组标记', exact: true }).waitFor();
          await page.getByRole('button', { name: '编辑分组备注', exact: true }).click();
          await page.getByLabel('分组名称', { exact: true }).fill('客户试听备选');
          await page.getByLabel('备注', { exact: true }).fill('第二版副歌更自然');
          await page.getByRole('dialog').getByRole('button', { name: /^保\s*存$/ }).click();
          await page.getByRole('dialog').waitFor({ state: 'hidden' });
          assert.equal(group.note, '第二版副歌更自然');
          await page.getByText('客户试听备选', { exact: true }).waitFor();
          await page.getByRole('button', { name: '加载试听', exact: true }).first().click();
          await page.waitForFunction(() => { const a = document.querySelector('audio'); return a && !a.paused && a.currentTime > 0; });
          const mini = page.getByRole('region', { name: '迷你播放器' });
          assert.equal(await mini.getByRole('button', { name: '上一首', exact: true }).isDisabled(), true);
          await mini.getByRole('button', { name: '下一首', exact: true }).click();
          await page.waitForFunction(() => document.querySelector('.mini-music-copy small')?.textContent.includes('2/2') && !document.querySelector('audio').paused);
          assert.equal(await mini.getByRole('button', { name: '下一首', exact: true }).isDisabled(), true);
          const source = await page.locator('audio').getAttribute('src');
          if (width === 390) await page.getByRole('button', { name: '打开导航', exact: true }).click();
          await page.getByRole('menuitem', { name: '自动流程', exact: true }).click();
          await page.waitForURL('**/workflows');
          await page.getByText('我的任务队列', { exact: true }).waitFor();
          if (width === 390) await page.getByRole('dialog').waitFor({ state: 'hidden' });
          assert.equal(await page.locator('audio').getAttribute('src'), source);
          await page.waitForFunction(() => !document.querySelector('audio').paused && document.querySelector('audio').currentTime > 0);
          await page.screenshot({ path: path.join(output, `player-${width}.png`), animations: 'allow' });
          await mini.getByRole('button', { name: '停止', exact: true }).click();
          assert.equal(await page.locator('audio').evaluate(a => a.paused && a.currentTime === 0), true);
        }
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
