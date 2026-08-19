// CDP-driven Yellosa scraper (paginated): pulls >10 businesses per city.
// Usage: CITY=pretoria TARGET=25 node scripts/scrape.js
// Requires puppeteer-core + system Chromium. Run from the project dir.
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const CHROME = '/snap/chromium/current/usr/lib/chromium-browser/chrome';
const OUT = process.env.OUT || '/root/scraper/pretoria_businesses.json';
const CITY = process.env.CITY || 'pretoria';
const TARGET = parseInt(process.env.TARGET || '25', 10);
const sleep = ms => new Promise(r => setTimeout(r, ms));

function absUrl(h){ return h.startsWith('http') ? h : 'https://yellosa.co.za' + h; }

async function collectLinks(browser, listPage){
  const seen = new Set();
  const links = [];
  let pageNum = 1;
  while (links.length < TARGET){
    const url = pageNum === 1
      ? `https://yellosa.co.za/location/${CITY}`
      : `https://yellosa.co.za/location/${CITY}?page=${pageNum}`;
    console.log(`[CDP] Listing page ${pageNum}: ${url}`);
    await listPage.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
    const hasGrid = await listPage.waitForSelector('a[href*="/company/"]', { timeout: 30000 }).then(()=>true).catch(()=>false);
    if (!hasGrid){ console.log('[CDP] No grid — stopping pagination.'); break; }
    const pageLinks = await listPage.$$eval('a[href*="/company/"]', as =>
      [...new Set(as.map(a => a.getAttribute('href')))].filter(h => /\/company\/\d+\//.test(h)));
    const before = links.length;
    for (const l of pageLinks){ const a = absUrl(l); if (!seen.has(a)){ seen.add(a); links.push(a); } }
    console.log(`[CDP] +${links.length - before} new (total ${links.length})`);
    if (links.length === before){ console.log('[CDP] No new links this page — stopping.'); break; }
    pageNum++;
    await sleep(1000);
  }
  return links.slice(0, TARGET);
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage']
  });
  const listPage = await browser.newPage();
  await listPage.setViewport({ width: 1280, height: 900 });

  const targets = await collectLinks(browser, listPage);
  console.log(`\n[CDP] Collected ${targets.length} business URLs. Scraping details...\n`);

  const businesses = [];
  const qaPage = await browser.newPage(); // reuse one page for all Q&A fetches
  for (let i = 0; i < targets.length; i++){
    const url = targets[i];
    console.log(`[CDP] ${i+1}/${targets.length} -> ${url}`);
    let data = null;
    try {
      const p = await browser.newPage();
      await p.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
      await p.waitForSelector('.cmp_details', { timeout: 20000 }).catch(()=>{});
      await sleep(700);

      data = await p.evaluate(() => {
        const field = (label) => {
          const lab = [...document.querySelectorAll('.cmp_details .info .label, .cmp_details .extra_info .info .label')]
            .find(l => l.textContent.replace(/\s+/g,' ').trim().toLowerCase().includes(label.toLowerCase()));
          if (!lab) return '';
          const info = lab.closest('.info') || lab.parentElement;
          const txt = (info.querySelector('.text') || info).textContent.replace(/\s+/g,' ').trim();
          return txt.replace(new RegExp('^'+label.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'i'),'').trim();
        };
        return {
          name: ((document.querySelector('#company_name')||document.querySelector('h1')||{}).textContent||'').trim() || document.title,
          address: ((document.querySelector('#company_address')||{}).textContent||'').replace(/\s+/g,' ').trim() || field('Address'),
          contact_number: field('Contact number'),
          mobile_phone: field('Mobile phone'),
          whatsapp: (document.querySelector('a[href*="wa.me"]')||{}).href || '',
          website: (document.querySelector('.text.weblinks a')||{}).href || '',
          establishment_year: field('Establishment year'),
          employees: field('Employees'),
          registration_code: field('Registration code'),
          company_description: ((document.querySelector('.text.desc')||{}).textContent||'').trim(),
          categories: [...document.querySelectorAll('.cmp_details .tags a')].map(a=>a.textContent.trim()),
          reviews: (document.querySelector('.reviews_count')||{}).textContent.replace(/\s+/g,' ').trim() || '',
          verified: !!document.querySelector('.vvv_verified'),
          premium: !!document.querySelector('.vvv_premium')
        };
      });

      const qIds = await p.evaluate(() =>
        [...new Set([...document.querySelectorAll('a[href*="/question/"]')]
          .map(a => (a.getAttribute('href').match(/\/question\/(\d+)/)||[])[1]).filter(Boolean))]);
      const qa = [];
      for (const qid of qIds){
        try {
          await qaPage.goto(`https://yellosa.co.za/question/${qid}`, { waitUntil: 'networkidle2', timeout: 45000 });
          await qaPage.waitForSelector('.content', { timeout: 10000 }).catch(()=>{});
          const pair = await qaPage.evaluate(() => {
            const c = document.querySelector('.content');
            if (!c) return { question:'', answer:'' };
            const txt = (c.innerText || '').replace(/\s+/g,' ').trim();
            const idx = txt.indexOf('Question for:');
            const seg = idx >= 0 ? txt.slice(idx) : txt;
            const qM = seg.match(/Posted on [\dA-Za-z, ]+?(.*?)(?:LISTING OWNER|PUBLIC USER|ANSWER)/i);
            const question = qM ? qM[1].replace(/\s+/g,' ').trim() : '';
            const aM = seg.match(/(?:LISTING OWNER|PUBLIC USER)[^\n]*?Posted on [\dA-Za-z, ]+?(.*?)ANSWER/i);
            const answer = aM ? aM[1].replace(/\s+/g,' ').trim() : '';
            return { question, answer };
          });
          qa.push(pair);
        } catch(e){ console.log(`[CDP]   Q&A ${qid} failed: ${e.message}`); qa.push({question:'',answer:''}); }
      }
      data.qa = qa;
      data.url = url;
      businesses.push(data);
      console.log(`[CDP]   ${data.name} | ☎${data.contact_number} 📱${data.mobile_phone} 🌐${data.website} | est:${data.establishment_year} emp:${data.employees} | rev:${data.reviews} | qa:${qa.length}`);
      await p.close();
    } catch(e){
      console.log(`[CDP]   BUSINESS FAILED: ${url} -> ${e.message}`);
      if (data) { data.url = url; data.error = e.message; businesses.push(data); }
      else businesses.push({ name:'(failed)', url, error:e.message });
    }
    await sleep(300);
  }
  await qaPage.close();

  fs.writeFileSync(OUT, JSON.stringify(businesses, null, 2));
  console.log(`\n[CDP] Saved ${businesses.length} businesses -> ${OUT}`);
  await browser.close();
})().catch(e => { console.error('ERROR:', e.message); process.exit(1); });
