const escapeHTML = (text) => String(text).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const list = document.querySelector('#projects');
if (list) {
  list.innerHTML = window.portfolioProjects.map((p, i) => `<article class="project-card ${i === 0 ? 'featured' : ''}"><a class="project-image" href="${escapeHTML(p.url)}" target="_blank" rel="noopener noreferrer" aria-label="查看 ${escapeHTML(p.name)}（新标签页）"><img src="${escapeHTML(p.image)}" alt="${escapeHTML(p.name)}的概念界面封面" ${i ? 'loading="lazy"' : 'fetchpriority="high"'} width="1200" height="600"></a><div class="project-info"><div class="project-kicker">${escapeHTML(p.category)}</div><h3 class="project-title" style="margin:0"><a href="${escapeHTML(p.url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(p.name)}</a></h3><p class="project-desc">${escapeHTML(p.description)}</p><div class="project-tags">${p.tags.map(t => `<span>${escapeHTML(t)}</span>`).join('')}</div><a class="project-arrow" href="${escapeHTML(p.url)}" target="_blank" rel="noopener noreferrer" aria-label="打开 ${escapeHTML(p.name)}（新标签页）">↗</a></div></article>`).join('');
}
const dialog = document.querySelector('#contact-dialog');
document.querySelector('#contact-button')?.addEventListener('click', () => dialog.showModal());
document.querySelectorAll('.close-dialog,.close-contact').forEach(button => button.addEventListener('click', () => dialog.close()));
dialog?.addEventListener('click', event => { if (event.target === dialog) { const r=dialog.getBoundingClientRect(); if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom) dialog.close(); } });
const detail = document.querySelector('#project-detail');
if (detail) {
  const id = new URLSearchParams(location.search).get('project');
  const p = window.portfolioProjects.find(item => item.id === id);
  if (!p) { detail.innerHTML = '<h1>还没找到这个作品。</h1><a class="pill" href="index.html#work">返回作品集 ↗</a>'; }
  else {
    document.title = `${p.name} — SunJX 作品概念`;
    detail.innerHTML = `<a class="back" href="index.html#work">← 返回全部作品</a><div class="detail-head"><p class="overline">${escapeHTML(p.category)} / CONCEPT DEMO</p><h1>${escapeHTML(p.name)}</h1><p>${escapeHTML(p.description)}</p><div class="project-tags">${p.tags.map(t=>`<span>${escapeHTML(t)}</span>`).join('')}</div></div><div class="detail-visual"><img src="${escapeHTML(p.image)}" alt="${escapeHTML(p.name)} 概念界面展示" width="1200" height="600"></div><div class="detail-body"><div class="detail-meta"><div><strong>项目类型</strong>个人概念作品 · 演示</div><div><strong>创作方向</strong>${escapeHTML(p.role)}</div><div><strong>年份</strong>${escapeHTML(p.year)}</div></div><div><h2>从一个想法开始。</h2><p>${escapeHTML(p.story)}</p><h2>让细节表达想法。</h2><p>${escapeHTML(p.design)}</p></div></div><div class="detail-bottom">你已经从主页跳转到了对应作品的示例页面。正式版本中，这个入口可以直接指向你的线上产品、独立作品站或项目详情页。<br><a href="index.html#work">继续浏览其他作品 →</a></div>`;
  }
}
