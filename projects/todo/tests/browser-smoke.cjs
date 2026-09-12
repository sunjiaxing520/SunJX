const { chromium, expect } = require('@playwright/test');
const fs = require('fs');
const base = process.env.TODO_URL || 'http://127.0.0.1:4175';
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const desktop = await browser.newContext({viewport:{width:1440,height:1000}});
  const mobile = await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const page = await desktop.newPage(), phone = await mobile.newPage();
  const errors=[];
  for(const p of [page,phone]) p.on('pageerror', e=>errors.push(e.message));
  const account={username:'qa_'+Date.now(),password:require('crypto').randomBytes(18).toString('hex'),name:'体验空间'};
  await page.goto(base);
  await page.getByRole('button',{name:'创建账号',exact:true}).click();
  await page.locator('[name=name]').fill(account.name);
  await page.locator('[name=username]').fill(account.username);
  await page.locator('[name=password]').fill(account.password);
  await page.getByRole('button',{name:'创建账号',exact:true}).click();
  await page.getByRole('button',{name:/先看看一份示例计划/}).click();
  await expect(page.getByText('看懂 HTML 的基本结构',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'AI 助手',exact:true}).click();
  await page.screenshot({path:'.runtime/desktop.png',fullPage:true});
  await page.getByRole('button',{name:'关闭 AI 助手'}).click();
  await phone.goto(base);
  await phone.locator('[name=username]').fill(account.username);
  await phone.locator('[name=password]').fill(account.password);
  await phone.getByRole('button',{name:'进入我的空间'}).click();
  await expect(phone.getByText('看懂 HTML 的基本结构',{exact:true})).toBeVisible();
  await page.getByLabel('添加待办内容').fill('跨设备同步验证');
  await page.getByLabel('添加待办内容').press('Enter');
  await expect(phone.getByText('跨设备同步验证',{exact:true})).toBeVisible({timeout:15000});
  await phone.screenshot({path:'.runtime/mobile.png',fullPage:true});
  await phone.getByText('跨设备同步验证',{exact:true}).click();
  await phone.getByLabel('备注',{exact:true}).fill('手机编辑，同步到电脑');
  await phone.getByRole('button',{name:'保存任务'}).click();
  await expect(phone.getByRole('dialog')).toHaveCount(0);
  await expect.poll(async()=>{const r=await desktop.request.get(base+'/api/state');return r.json().then(s=>s.tasks.find(t=>t.title==='跨设备同步验证')?.notes)}).toBe('手机编辑，同步到电脑');
  for(const width of [320,390,768,1440]){
    await page.setViewportSize({width,height:900});
    for(const view of ['今天','我的计划','日历','复盘','设置']){
      const nav=width<760?page.locator('.mobile-bottom'):page.locator('.sidebar');
      await nav.getByRole('button',{name:new RegExp(view==='复盘'?'学习复盘|复盘':view)}).first().click();
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
      if(overflow)throw new Error(`Horizontal overflow: ${width} ${view}`);
    }
  }
  await phone.getByRole('button',{name:'AI 助手',exact:true}).click();
  await expect(phone.getByRole('complementary',{name:'AI 计划助手'})).toBeVisible();
  await phone.screenshot({path:'.runtime/mobile-ai.png',fullPage:true});
  if(errors.length)throw new Error(errors.join('\n'));
  fs.writeFileSync('.runtime/qa-account.json',JSON.stringify(account));
  await browser.close();
  console.log('PASS: registration, no-key Todo, sample plan, two-context sync, mobile edit, 4 widths × 5 views, mobile AI, no page errors.');
})().catch(e=>{console.error(e);process.exit(1)});
