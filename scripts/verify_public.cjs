/* Verify the actual public deployment after GitHub Pages reports success. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.SOLARTRACK_PLAYWRIGHT||'playwright');
const root=path.resolve(__dirname,'..');
const base=(process.env.SOLARTRACK_PUBLIC_URL||'https://khachatryann.github.io/solartrack-lab/').replace(/\/?$/,'/');
async function main(){
  const browser=await chromium.launch({headless:true});
  const report={url:base,checked_at_utc:new Date().toISOString(),checks:[]};
  const errors=[];
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1050}});
    page.on('pageerror',e=>errors.push(e.message));
    const response=await page.goto(base);assert.equal(response.status(),200);
    await page.waitForFunction(()=>!document.getElementById('download').disabled);
    report.checks.push('Public homepage returns HTTP 200 and loads the recorded dashboard');
    const verification=await page.request.get(base+'data/verification.json');assert.equal(verification.status(),200);
    const v=await verification.json();assert(v.passed);assert.equal(v.comparison_points,5050);
    report.checks.push('Public verification data passes and contains all 5050 comparison points');
    await page.selectOption('#scenario','noise');await page.selectOption('#step','0.2');await page.selectOption('#sample','0.5');
    await page.waitForFunction(()=>document.getElementById('download-json').getAttribute('href')==='data/runs/noise-step0.2-sample0.5.json'&&!document.getElementById('download').disabled);
    const local=JSON.parse(fs.readFileSync(path.join(root,'results/runs/noise-step0.2-sample0.5.json')));
    const values=await page.locator('.metric-main').allTextContents();Object.values(local.controllers).forEach((c,i)=>assert.equal(parseFloat(values[i]),+c.metrics.tracking_pct.toFixed(2)));
    report.checks.push('Public scenario and tuning changes match the corresponding generated results');
    const [download]=await Promise.all([page.waitForEvent('download'),page.click('#download')]);
    assert.equal(fs.readFileSync(await download.path(),'utf8').trim().split('\n').length,3604);
    report.checks.push('Public selected CSV download contains all 3603 controller/time rows');
    await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.click('#reset');await page.click('#play');await page.waitForTimeout(450);await page.click('#play');assert(+(await page.inputValue('#timeline'))>0);
    report.checks.push('Public mobile layout and playback work');
    const methods=await page.goto(base+'methodology.html#verification');assert.equal(methods.status(),200);assert.equal(await page.locator('#verification').count(),1);
    report.checks.push('Public methodology and verification deep link work');
    assert.deepEqual(errors,[]);report.checks.push('No public browser script errors');
    report.passed=true;
    fs.writeFileSync(path.join(root,'docs/public-qa.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify(report,null,2));
  }finally{await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
