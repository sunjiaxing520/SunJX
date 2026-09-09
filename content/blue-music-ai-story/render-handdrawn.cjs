const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const spec = JSON.parse(fs.readFileSync(path.join(__dirname,'handdrawn-preview.json'),'utf8'));
const esc = text => text.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('\n','<br>');
async function main() {
  fs.mkdirSync(path.join(spec.output,'frames'),{recursive:true});
  const screenshot = fs.readFileSync(path.resolve(__dirname,'../../projects/blue-music-platform/logs/provider-presets-ui/390-preset.png')).toString('base64');
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
    for (let i=0;i<3;i++) {
      const s=spec.scenes[i];
      const content = i===0 ? `<div class="shot"><div class="tape"></div><img src="data:image/png;base64,${screenshot}"></div><div class="handnote">不是教程作业。</div>` :
        i===1 ? '<div class="quote"><small>我问 AI：</small><p><span class="english">pytest</span> 是一个命令吗，<br>还是文件</p><div class="underline"></div></div><div class="aside">从这些问题开始。</div>' :
        '<div class="steps"><div>我说需求</div><b>↓</b><div>AI 帮着实现</div><b>↓</b><div>我再检查</div></div><div class="aside">不是一句话就做完。</div>';
      await page.setContent(`<!doctype html><meta charset="utf-8"><style>
      *{box-sizing:border-box}body{margin:0;width:1080px;height:1920px;overflow:hidden;background-color:#f6f7f9;background-image:linear-gradient(#d9e0e752 1px,transparent 1px),linear-gradient(90deg,#d9e0e752 1px,transparent 1px);background-size:38px 38px;color:#20272d;font-family:'KaiTi','STKaiti','Microsoft YaHei',sans-serif}
      body:before{content:'';position:absolute;left:48px;top:0;bottom:0;width:2px;background:#eea5a280}
      header{position:absolute;left:90px;right:115px;top:122px;display:flex;justify-content:space-between;font-size:30px;color:#426f79;font-weight:bold}
      h1{position:absolute;left:94px;right:110px;top:230px;margin:0;font-size:104px;line-height:1.28;transform:rotate(-1deg);font-weight:bold}
      h1:after{content:'';display:block;width:440px;height:13px;margin-top:17px;background:#f3ce4b;transform:rotate(-1.3deg);border-radius:42% 20% 55% 10%}
      main{position:absolute;left:100px;right:120px;top:580px;height:815px}
      .shot{position:relative;width:455px;height:786px;margin:0 auto;border:4px solid #27363c;box-shadow:8px 8px 0 #d5e4e7;border-radius:4px 12px 5px 8px;transform:rotate(-1deg);background:white;overflow:visible}
      .shot img{width:100%;height:100%;object-fit:cover;object-position:50% 27%;border-radius:3px}.tape{position:absolute;z-index:2;top:-20px;left:118px;width:198px;height:44px;background:#f5d758d9;transform:rotate(-3deg)}
      .handnote{position:absolute;bottom:-65px;right:48px;font-size:42px;color:#b14d42;transform:rotate(-3deg)}
      .quote{margin-top:150px;position:relative;padding:45px 22px 60px;border-top:3px solid #34474f;border-bottom:3px solid #34474f;transform:rotate(-1deg)}.quote:before{content:'';position:absolute;inset:-7px 6px 3px -6px;border-top:1px solid #67777b;border-bottom:1px solid #67777b;pointer-events:none}
      .quote small{font-size:40px;color:#487986}.quote p{font-size:64px;line-height:1.7;margin:30px 0 0;font-weight:bold}.english{font-family:'Segoe Print',sans-serif;color:#aa443d}.underline{width:300px;height:10px;background:#edc742;transform:rotate(-2deg)}
      .aside{margin-top:70px;font-size:46px;color:#477c88;transform:rotate(-2deg)}
      .steps{padding-top:15px;text-align:center}.steps div{display:inline-block;padding:15px 45px;border:3px solid #34484f;border-radius:5px 15px 5px 10px;font-size:60px;transform:rotate(-1deg);background:#ffffffc9}.steps div:nth-of-type(2){transform:rotate(1deg);border-color:#b95746;background:#fff5dc}.steps b{display:block;font-size:67px;line-height:1.15;color:#477c88}
      .note{position:absolute;left:95px;right:112px;top:1504px;font-size:29px;line-height:1.6;color:#526a75}.note:before{content:'';display:block;width:100%;border-top:2px dashed #9bacb3;margin-bottom:22px}
      footer{position:absolute;left:95px;right:115px;bottom:98px;display:flex;justify-content:space-between;font-size:27px;color:#6c7c84}
      </style><header><span>${esc(s.label)}</span><span>0${i+1}</span></header><h1>${esc(s.title)}</h1><main>${content}</main><div class="note">${esc(s.note)}</div><footer><span>10秒风格小样 / 无人物</span><span>AI合成旁白</span></footer>`);
      await page.evaluate(()=>document.fonts.ready);
      await page.screenshot({path:path.join(spec.output,'frames',`${i}.png`)});
    }
  } finally { await browser.close(); }
  console.log('3 handdrawn-note frames rendered; original screenshot retained');
}
main().catch(e=>{console.error(e);process.exitCode=1});
