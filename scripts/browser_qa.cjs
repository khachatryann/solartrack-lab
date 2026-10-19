/* Browser verification of generated local artifacts, not the user's browser. */
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const assert=require('node:assert/strict');
const {chromium}=require(process.env.SOLARTRACK_PLAYWRIGHT || 'playwright');
const root=path.resolve(__dirname,'..'), dist=path.join(root,'dist'), evidence=path.join(root,'docs');
const types={'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.zip':'application/zip','.csv':'text/csv','.md':'text/plain','.xml':'application/xml'};
const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost');let name=decodeURIComponent(url.pathname);if(name.endsWith('/'))name+='index.html';
  const file=path.resolve(dist,'.'+name);
  if(!file.startsWith(dist+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end('Not found');return;}
  res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);
});
const report={tool:'Playwright',version:require((process.env.SOLARTRACK_PLAYWRIGHT||'playwright')+'/package.json').version,mobile_method:'Chromium viewport emulation; not physical devices',checks:[],screenshots:[]};
const check=(name)=>{report.checks.push({name,passed:true});console.log('PASS '+name);};
async function waitRun(page,scenario,step,sample){const expected=`data/runs/${scenario}-step${step}-sample${sample}.json`;await page.waitForFunction(href=>document.getElementById('download-json').getAttribute('href')===href&&!document.getElementById('download').disabled,expected);}
async function main(){
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url=`http://127.0.0.1:${server.address().port}`;
  const browser=await chromium.launch({headless:true});
  const errors=[];
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1050},deviceScaleFactor:1});
    page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
    await page.goto(url);await waitRun(page,'drop','0.6','0.25');
    assert.equal(await page.locator('.metric-card').count(),3);
    check('Dashboard loads all three controller metrics');
    const summary=JSON.parse(fs.readFileSync(path.join(root,'results/summary.json'),'utf8'));
    for(const scenario of ['constant','drop','ramp','clouds','temperature','noise']){
      await page.selectOption('#scenario',scenario);
      for(const step of ['0.2','0.6','1.2'])for(const sample of ['0.1','0.25','0.5']){
        await page.selectOption('#step',step);await page.selectOption('#sample',sample);await waitRun(page,scenario,step,sample);
        const expected=summary.filter(r=>r.scenario===scenario&&r.step_v===+step&&r.sample_s===+sample);
        const values=await page.locator('.metric-main').allTextContents();
        expected.forEach((r,i)=>assert.equal(parseFloat(values[i]),+r.tracking_pct.toFixed(2)));
      }
    }
    check('All 54 scenario/tuning selections load actual generated metrics');
    await page.selectOption('#scenario','drop');await page.selectOption('#step','0.6');await page.selectOption('#sample','0.25');await waitRun(page,'drop','0.6','0.25');
    for(const signal of ['p','v','g','tc','energy_wh']){await page.click(`[data-signal="${signal}"]`);assert(await page.locator('#timeline-chart svg title').textContent());}
    await page.click('[data-signal="p"]');check('All five timeline signals render accessible named charts');
    await page.click('[data-curve="iv"]');assert.match(await page.locator('#curve-chart svg>title').textContent(),/current versus voltage/);
    await page.click('[data-curve="pv"]');check('I–V and P–V curve switching');
    const before=await page.locator('#timeline-chart svg>path').count();await page.uncheck('[data-controller="po"]');
    assert.equal(await page.locator('#timeline-chart svg>path').count(),before-1);await page.check('[data-controller="po"]');check('Controller visibility changes plotted series');
    await page.click('#reset');assert.equal(await page.inputValue('#timeline'),'0');
    await page.click('#play');await page.waitForTimeout(650);await page.click('#play');const paused=await page.inputValue('#timeline');assert(+paused>0);await page.waitForTimeout(250);assert.equal(await page.inputValue('#timeline'),paused);
    await page.locator('#timeline').fill('128');await page.locator('#timeline').dispatchEvent('input');assert.match(await page.locator('#curve-time').textContent(),/32.00/);check('Play, pause, reset and exact timeline inspection');
    await page.locator('.data-details summary').click();const cells=await page.locator('#snapshot tr').first().locator('td').allTextContents();
    const run=JSON.parse(fs.readFileSync(path.join(root,'results/runs/drop-step0.6-sample0.25.json'),'utf8'));
    assert.equal(+cells[2],+run.controllers.fixed.series.p[640].toFixed(4));await page.locator('.data-details summary').click();check('Electrical inspection table matches the selected raw timestep');
    const [download]=await Promise.all([page.waitForEvent('download'),page.click('#download')]);const csv=fs.readFileSync(await download.path(),'utf8');assert.equal(csv.trim().split('\n').length,3604);assert(csv.includes('oracle_energy_wh'));check('Selected CSV downloads all 3603 controller/time rows');
    await page.selectOption('#sweep-controller','inc');await page.click('.sweep-cell[data-step="1.2"][data-sample="0.5"]');await waitRun(page,'drop','1.2','0.5');check('Parameter sweep loads its real configuration');
    await page.selectOption('#step','0.6');await page.selectOption('#sample','0.25');await waitRun(page,'drop','0.6','0.25');await page.selectOption('#sweep-controller','po');
    fs.mkdirSync(path.join(evidence,'screenshots'),{recursive:true});
    await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(evidence,'screenshots/desktop.png'),fullPage:true});
    await page.screenshot({path:path.join(evidence,'screenshots/desktop-viewport.png')});report.screenshots.push({path:'docs/screenshots/desktop.png',viewport:{width:1440,height:1050}});
    for(const width of [375,390,768,1440]){
      await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Horizontal overflow at ${width}px`);
    }
    check('No page overflow at 375, 390, 768 and 1440 CSS pixels');
    await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(evidence,'screenshots/mobile.png'),fullPage:true});
    report.screenshots.push({path:'docs/screenshots/mobile.png',viewport:{width:390,height:844}});
    await page.selectOption('#scenario','noise');await waitRun(page,'noise','0.6','0.25');await page.click('#play');await page.waitForTimeout(200);await page.click('#play');check('Mobile scenario and playback controls work');
    for(const name of ['methodology','learning','report','verification']){
      const response=await page.goto(`${url}/${name}.html`);assert.equal(response.status(),200);assert(await page.locator('h1').count()>0);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Documentation overflow: ${name}`);
    }
    check('Methodology, learning guide, technical report and verification pages render on mobile');
    await page.goto(`${url}/methodology.html#verification`);assert.equal(await page.locator('#verification').count(),1);check('Verification deep link resolves');
    assert.deepEqual(errors,[]);check('No browser script or console errors');
    report.passed=true;report.configuration_selections=54;report.browser='Chromium '+browser.version();
  }finally{await browser.close();server.close();fs.writeFileSync(path.join(evidence,'browser-qa.json'),JSON.stringify(report,null,2)+'\n');}
}
main().catch(error=>{console.error(error);server.close();process.exitCode=1;});
