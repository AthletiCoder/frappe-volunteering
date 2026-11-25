import fs from 'node:fs';
import { expect, test } from '@playwright/test';

// Explicit opt-in fixtures prevent HR writes on a review/production database.
const path = process.env.E2E_HR_FIXTURES;
const fixtures = path ? JSON.parse(fs.readFileSync(path, 'utf8')) : null;
test.skip(!fixtures, 'Requires isolated HR test fixtures.');
test.beforeEach(async ({baseURL}) => {
  if (!baseURL || !['localhost','127.0.0.1'].includes(new URL(baseURL).hostname)) throw new Error('HR regression must use an isolated local site.');
});

for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
 test.describe(`${viewport.width}px time and leave`,()=>{
  test.use({viewport});
  test('employee requests are submitted and manager can approve them', async ({page})=>{
   const request=page.request;
   const login = async(key:string)=>{const u=fixtures.users[key];const r=await request.post('/api/method/login',{form:{usr:u.email,pwd:u.password}});expect(r.ok()).toBeTruthy();};
   await login('employee');await page.goto('/volunteering/time-leave');
   await expect(page.getByRole('heading',{name:'Time and leave',exact:true})).toBeVisible();
   await expect(page.getByRole('tab',{name:'HR policy & balances'})).toHaveCount(0);
   await page.getByRole('button',{name:'New request',exact:true}).first().click();
   await page.getByLabel('Request type',{exact:true}).selectOption('WFH');
   const used=await page.evaluate(async()=>{const r=await fetch('/api/method/volunteering.volunteering.time_leave_portal.get_time_workspace',{method:'POST',headers:{'Content-Type':'application/json','X-Frappe-CSRF-Token':(window as any).csrf_token||''},body:'{}'});return (await r.json()).message.requests.filter((x:any)=>x.type==='WFH' && ['Open','Approved'].includes(x.status)).map((x:any)=>x.from_date);});
   const date=new Date();date.setDate(date.getDate()+25);let day='';
   do {day=[date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),String(date.getDate()).padStart(2,'0')].join('-');date.setDate(date.getDate()+1);}while(used.includes(day));
   await page.getByLabel('From date',{exact:true}).fill(day);await page.getByLabel('To date',{exact:true}).fill(day);
   const reason=`Remote preparation of learning materials ${viewport.width}px regression ${Date.now()}`;
   await page.getByLabel('Reason',{exact:true}).fill(reason);
   await page.getByRole('button',{name:'Submit request',exact:true}).click();
   await expect(page.getByRole('status')).toContainText('Request saved');
   await expect(page.locator('p.whitespace-pre-wrap').filter({hasText:reason})).toBeVisible();
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
   await page.screenshot({path:`output/hr-policy-20261124/employee-${viewport.width}.png`,fullPage:true});
   await login('manager');await page.goto('/volunteering/time-leave?view=team');
   await expect(page.getByRole('tab',{name:'Team review'})).toHaveAttribute('aria-selected','true');
   await page.getByRole('button').filter({hasText:reason}).click();
   await page.getByRole('button',{name:'Approve',exact:true}).click();
   await expect(page.getByRole('status')).toContainText('Decision recorded');
   await expect(page.getByRole('button').filter({hasText:reason})).toContainText('Approved');
  });
  test('HR can inspect policy history and make a reasoned balance adjustment',async({page})=>{
   const request=page.request;
   const u=fixtures.users.hr;expect((await request.post('/api/method/login',{form:{usr:u.email,pwd:u.password}})).ok()).toBeTruthy();
   await page.goto('/volunteering/time-leave?view=policy');
   await expect(page.getByRole('heading',{name:'Policy history',exact:true})).toBeVisible();
   await expect(page.getByLabel('First month of leave year',{exact:true})).toHaveValue('1');
   await expect(page.getByLabel('Weekly off',{exact:true})).toHaveValue('6');
   await expect(page.getByLabel('Paid leave earned each month',{exact:true})).toHaveValue('2.5');
   const december=page.getByRole('heading',{name:'Policy history',exact:true}).locator('..').locator('div.border-t').filter({hasText:'Team policy charter effective 1 December 2026'});
   await december.getByRole('button',{name:'Use as starting values',exact:true}).click();
   await expect(page.getByLabel('Days allowed to log work',{exact:true})).toHaveValue('4');
   await expect(page.getByLabel('Minimum hours for a half working day',{exact:true})).toHaveValue('3');
   await page.getByLabel('Employee',{exact:true}).selectOption(fixtures.employees.employee);
   await page.getByRole('button',{name:'Preview current balance',exact:true}).click();
   await expect(page.getByText('Current balance:',{exact:false})).toBeVisible();
   await page.getByLabel('Reason',{exact:true}).fill(`Verified HR regression balance correction ${viewport.width}px`);
   await page.getByLabel('Adjust by days',{exact:false}).fill('0.5');
   await page.getByRole('button',{name:'Post balance adjustment',exact:true}).click();
   await expect(page.getByRole('status')).toContainText('Reasoned leave adjustment posted');
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
   await page.screenshot({path:`output/hr-policy-20261124/hr-${viewport.width}.png`,fullPage:true});
  });
 });
}
