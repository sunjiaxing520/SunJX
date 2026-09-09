const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const story = JSON.parse(fs.readFileSync(path.join(__dirname, 'story.json'), 'utf8'));
const escape = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const lines = s => escape(s).replaceAll('\n','<br>');
const assets = path.resolve(__dirname, '../../projects/blue-music-platform/logs/provider-presets-ui');
async function main() {
  fs.mkdirSync(path.join(story.output, 'frames'), { recursive:true });
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
    for (const [i, scene] of story.scenes.entries()) {
      let content = '';
      if (scene.quote) content = `<div class="quote"><span>我 / 开发时的提问与要求</span><p>${escape(scene.quote)}</p><b>人提出问题，AI协助实现。</b></div>`;
      if (scene.image) {
        const data = fs.readFileSync(path.join(assets, scene.image)).toString('base64');
        content = `<div class="shot ${scene.image.startsWith('1440')?'desktop':'mobile'}"><img src="data:image/png;base64,${data}"></div>`;
      }
      if (scene.kind==='issues') content = '<div class="issues"><article><em>01 / 密钥边界</em><h2>换了供应商<br>却可能沿用旧密钥</h2></article><article><em>02 / 测试一致性</em><h2>改了配置<br>旧测试却可能仍算通过</h2></article></div>';
      if (scene.kind==='tests') content = '<div class="counts"><div><strong>180</strong><span>后端测试通过</span></div><div><strong>37</strong><span>前端测试通过</span></div></div><div class="commit">已修补：密钥隔离 / 配置版本校验<br>严格连接校验 / 保存并测试</div>';
      if (scene.kind==='status') content = '<div class="status"><div><b>已经实现</b><p>工作台 · 作词 · 审核<br>记忆 · 收藏 · 接口配置</p></div><div><b>仍需验证</b><p>新音乐接口<br>真实生成与回调联调</p></div></div>';
      if (scene.kind==='ending') content = '<div class="end"><span>不是一句话做完。</span><strong>是一次次卡住，<br>还能继续。</strong><i>我提需求 / AI协助 / 我来判断</i></div>';
      await page.setContent(`<!doctype html><meta charset="utf-8"><style>
        *{box-sizing:border-box}body{margin:0;width:1080px;height:1920px;background:#111315;color:#f4f4ef;font-family:'Microsoft YaHei',sans-serif;letter-spacing:0;overflow:hidden}
        .rail{height:12px;position:absolute;top:0;left:0;background:#d9fb65;width:${(i+1)/story.scenes.length*100}%}
        header{position:absolute;top:130px;left:76px;right:96px;display:flex;justify-content:space-between;color:#d9fb65;font-size:27px;font-weight:700}
        h1{position:absolute;left:76px;right:100px;top:210px;margin:0;font-size:76px;line-height:1.28;font-weight:900}
        main{position:absolute;left:76px;right:104px;top:475px;height:870px}
        .quote{margin-top:110px;border-top:3px solid #d9fb65;border-bottom:1px solid #52565b;padding:46px 0}
        .quote span{font-size:29px;color:#9ca6ab}.quote p{font-size:62px;line-height:1.5;font-weight:700;margin:35px 0 50px;text-wrap:balance}.quote b{font-size:28px;color:#d9fb65}
        .shot{height:860px;overflow:hidden;background:#f9f9fa;border-radius:6px}.shot img{display:block}.desktop img{height:860px;width:auto;transform:translateX(-260px)}.mobile{width:540px;margin:auto}.mobile img{width:540px;height:auto;transform:translateY(-112px)}
        .issues article{padding:36px 0;border-bottom:1px solid #505559}.issues em{font-size:30px;font-style:normal;color:#ff897b}.issues h2{font-size:51px;line-height:1.45;margin:24px 0}
        .counts{display:flex;gap:70px;margin-top:65px}.counts div{flex:1}.counts strong{display:block;font-size:164px;color:#d9fb65;line-height:1.2}.counts span{font-size:34px}.commit{margin-top:80px;padding-top:36px;border-top:1px solid #505559;line-height:1.9;font-size:34px;color:#b9c5cc}
        .status>div{padding:34px 0;border-bottom:1px solid #505559}.status b{font-size:32px;color:#d9fb65}.status>div+div b{color:#ffad92}.status p{font-size:46px;line-height:1.6;margin:16px 0}
        .end{padding-top:125px}.end span{font-size:40px;color:#a9b3b8}.end strong{display:block;font-size:77px;line-height:1.45;color:#d9fb65;margin:40px 0}.end i{font-style:normal;font-size:30px;color:#b9c5cc}
        .note{position:absolute;left:76px;right:104px;top:1410px;font-size:27px;line-height:1.65;color:#abb4b9;border-top:1px solid #43494c;padding-top:24px}
        footer{position:absolute;bottom:94px;left:76px;right:104px;color:#7e898f;font-size:24px;display:flex;justify-content:space-between}
      </style><div class="rail"></div><header><span>${escape(scene.label)}</span><span>0${i+1} / 09</span></header><h1>${lines(scene.title)}</h1><main>${content}</main><div class="note">${lines(scene.note)}</div><footer><span>蓝乐 · 真实项目开发记录</span><span>AI 合成旁白</span></footer>`);
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({path:path.join(story.output,'frames',`${String(i).padStart(2,'0')}.png`)});
    }
  } finally { await browser.close(); }
  console.log('Rendered 9 verified-source vertical frames');
}
main().catch(e=>{console.error(e);process.exitCode=1});
