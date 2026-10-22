import {chromium} from '../../promo-video/node_modules/playwright-core/index.mjs';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--disable-web-security']});
const page=await browser.newPage({viewport:{width:1600,height:900},deviceScaleFactor:1});
await page.goto('http://127.0.0.1:4178/media/hyperframes-video/capture.html');await page.waitForFunction(()=>window.ready);
const evidence={};
for(const [name,params] of Object.entries({'c3':['C3'],'d3':['D3'],'c3-samples':['C3','theatre','seat',true],'overview':['C3','theatre','overview'],'a2-theatre':['A2'],'a2-concert':['A2','concert'],'vlm-overview':['C3','theatre','overview',false,true]})){
 evidence[name]=await page.evaluate(p=>window.shot(...p),params);await page.waitForTimeout(150);await page.screenshot({path:`media/hyperframes-video/assets/${name}.png`});
}
// Video-only camera framing of the unmodified product renderer and VLM model.
await page.evaluate(()=>window.shot('C3','theatre','overview',false,true));await page.waitForTimeout(150);
await page.evaluate(()=>{const v=window.viewer;v.camera.position.set(13,18,19);v.camera.lookAt(0,1.8,5.5);v.camera.fov=44;v.camera.updateProjectionMatrix();v.renderer.render(v.scene,v.camera);});
await page.screenshot({path:'media/hyperframes-video/assets/vlm-overview.png'});
await page.goto('http://127.0.0.1:4178/index.html');await page.waitForSelector('canvas');await page.waitForTimeout(700);await page.screenshot({path:'media/hyperframes-video/assets/product.png'});
await page.locator('#pick-compare').click();await page.locator('[data-seat="17"]').click();await page.waitForTimeout(200);await page.screenshot({path:'media/hyperframes-video/assets/product-compare.png'});
await writeFile('media/hyperframes-video/capture/calculation-evidence.json',JSON.stringify(evidence,null,2));
await browser.close();console.log('Captured actual VenueViewer and product UI; calculated source evidence saved.');
