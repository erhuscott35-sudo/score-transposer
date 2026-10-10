// Run after npm test. Optional Playwright installation and local app server required.
import fs from 'node:fs';
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SCORE_PLAYWRIGHT_MODULE||'playwright');
const {toXML}=await import('../test-output/xml.mjs');
const sample=JSON.parse(fs.readFileSync('lib/sample.json'));
const score={...sample,sourcePageCount:2,measures:[...sample.measures.map(m=>({...m,sourcePage:1})),...sample.measures.map(m=>({...m,number:m.number+27,sourcePage:2}))]};
const xml=toXML(score);
const browser=await chromium.launch({headless:true,...(process.env.SCORE_CHROME_PATH?{executablePath:process.env.SCORE_CHROME_PATH}:{})});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let jobs=0,cancelled=false,deletes=0;
 await page.route('http://127.0.0.1:8765/api/**',async route=>{
   const req=route.request();let body;
   if(req.url().endsWith('/health'))body={apiVersion:3,ready:true};
   else if(req.method()==='POST'){jobs++;cancelled=false;body={id:'a'.repeat(32)};}
   else if(req.method()==='DELETE'){deletes++;cancelled=true;body={state:'cancelled'};}
   else if(jobs===1)body={state:'succeeded',result:{xml,pageCount:2}};
   else body={state:cancelled?'cancelled':'running',message:'正在辨識整份樂譜（共 2 頁）',elapsedSeconds:2};
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body),headers:{'Access-Control-Allow-Origin':'*'}});
 });
 await page.goto(process.env.SCORE_TEST_URL||'http://localhost:3000/');
 await page.locator('.paper svg').first().waitFor();
 await page.locator('input[type=file]').setInputFiles('test-output/two-pages.pdf');
 await page.getByText('第 2 頁已核對',{exact:false}).waitFor();
 assert.equal(await page.locator('.page-reviews input:checked').count(),0);
 assert.equal(await page.getByRole('button',{name:/下載 .* 調 PDF/}).isDisabled(),true);
 await page.getByRole('checkbox',{name:'第 1 頁已核對'}).check();
 await page.getByRole('checkbox',{name:'第 2 頁已核對'}).check();
 await page.getByRole('button',{name:'對照小節 1–27'}).click();
 assert.equal(await page.getByAltText('原始樂譜第 1 頁').isVisible(),true);
 await page.getByLabel('音符 2 歌詞',{exact:true}).fill('核');
 assert.equal(await page.getByRole('checkbox',{name:'第 1 頁已核對'}).isChecked(),false);
 assert.equal(await page.getByRole('checkbox',{name:'第 2 頁已核對'}).isChecked(),true);
 await page.getByRole('checkbox',{name:'第 1 頁已核對'}).check();
 await page.getByRole('button',{name:/移調預覽/}).click();
 await page.getByRole('button',{name:/下載 .* 調 PDF/}).waitFor();
 const download=page.waitForEvent('download');
 await page.getByRole('button',{name:/下載 .* 調 PDF/}).click();
 await (await download).saveAs('test-output/browser-two-pages.pdf');
 await page.screenshot({path:'test-output/workflow-browser.png',fullPage:true});
 await page.locator('input[type=file]').setInputFiles('test-output/two-pages.pdf');
 await page.getByRole('status').filter({hasText:'已用 2 秒'}).waitFor();
 const before=deletes;
 await page.getByRole('button',{name:'取消辨識',exact:true}).click();
 await page.getByRole('status').filter({hasText:'已取消辨識'}).waitFor();
 assert.ok(deletes>before);
 assert.equal(await page.locator('input[type=file]').isDisabled(),false);
 assert.deepEqual(errors,[]);
 console.log('PASS browser: two-page import, review invalidation, PDF download, progress and cancel');
}finally{await browser.close();}
