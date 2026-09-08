import { chromium } from '@playwright/test';
const browser = await chromium.launch({channel:'msedge', headless:true});
const page = await browser.newPage({viewport:{width:1366,height:900}});
page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
page.on('console', msg => { if(msg.type()==='error')console.log('CONSOLE ERROR:',msg.text()); });
page.on('requestfailed', req => console.log('REQUEST FAILED:',req.url(),req.failure()?.errorText));
try {
 await page.goto('http://127.0.0.1:8000/?diagnostic=1',{waitUntil:'networkidle'});
 console.log('TITLE:',await page.title());
 await page.getByRole('heading',{name:'Спросите ваши данные'}).waitFor();
 await page.getByRole('button',{name:'Данные и правила'}).click();
 await page.getByRole('heading',{name:'Данные и бизнес-правила'}).waitFor();
 await page.getByRole('button',{name:'ИИ-аналитика'}).click();
 console.log('Main screen and catalog navigation: PASS');
 await page.screenshot({path:'browser-check.png',fullPage:true});
 const embed = await browser.newPage();
 await embed.setContent('<iframe src="http://127.0.0.1:8000/?embed-check=1" style="width:1200px;height:850px"></iframe>');
 await embed.frameLocator('iframe').getByRole('heading',{name:'Спросите ваши данные'}).waitFor({timeout:15000});
 console.log('Embedded frame rendering: PASS');
} finally {await browser.close();}
