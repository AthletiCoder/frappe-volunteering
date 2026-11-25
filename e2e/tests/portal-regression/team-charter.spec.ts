import fs from 'node:fs';
import {expect,test} from '@playwright/test';
const fixturePath=process.env.E2E_HR_FIXTURES;
const fixture=fixturePath?JSON.parse(fs.readFileSync(fixturePath,'utf8')):null;
test.skip(!fixture,'Requires isolated HR fixtures.');
test.beforeEach(({baseURL})=>{if(!baseURL||!['localhost','127.0.0.1'].includes(new URL(baseURL).hostname))throw new Error('Use an isolated local site.');});
async function login(page:any,who:string){const u=fixture.users[who];expect((await page.request.post('/api/method/login',{form:{usr:u.email,pwd:u.password}})).ok()).toBeTruthy();}
async function call(page:any,method:string,args:any={}){return page.evaluate(async({method,args}:any)=>{const response=await fetch('/api/method/volunteering.volunteering.'+method,{method:'POST',headers:{'Content-Type':'application/json','X-Frappe-CSRF-Token':(window as any).csrf_token||''},body:JSON.stringify(args)});if(!response.ok)throw new Error(await response.text());return (await response.json()).message;},{method,args});}
for(const width of [1440,390])test.describe(`${width}px revised team charter`,()=>{
 test.use({viewport:{width,height:1000}});
 test('employee sees guide and HR can publish a holiday and payroll profile',async({page})=>{
  await login(page,'employee');await page.goto('/volunteering/time-leave');
  await page.getByRole('tab',{name:'People centre',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Team policy charter',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:/^(Organisation( and reporting)?|Where we work)$/i})).toHaveCount(0);
  for(const name of ['Work logs and attendance','Paid leave and approvals','Compensatory leave','Medical leave','Parental leave','Salary and deductions','Working arrangements']){
   await expect(page.getByRole('heading',{name,exact:true})).toHaveCount(1);
  }
  expect(await page.locator('.guide-points > li').count()).toBeGreaterThan(20);
  await expect(page.getByRole('heading',{name:'Who to contact',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Payroll',exact:true})).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`output/team-charter-20261125/guide-${width}.png`,fullPage:true});
  await login(page,'hr');await page.goto('/volunteering/time-leave');
  await page.getByRole('tab',{name:'People centre',exact:true}).click();
  await page.getByRole('button',{name:'Holidays',exact:true}).click();
  const name=`Charter optional ${width} ${Date.now()}`;
  const calendar=await call(page,'hr_resources.get_people_centre',{year:2027});
  const used=new Set(calendar.holidays.map((row:any)=>row.holiday_date));
  const dateValue=new Date('2027-11-01T12:00:00');
  while(used.has(dateValue.toISOString().slice(0,10)))dateValue.setDate(dateValue.getDate()+1);
  const date=dateValue.toISOString().slice(0,10);
  await page.getByLabel('Holiday name',{exact:true}).fill(name);
  await page.getByLabel('Date',{exact:true}).fill(date);
  await page.getByLabel('Holiday type',{exact:true}).selectOption('Optional');
  await page.getByLabel('Reason for calendar change',{exact:true}).fill('Confirmed optional holiday date for portal regression');
  await page.getByRole('button',{name:'Save holiday',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Holiday calendar updated');
  await expect(page.getByText(name,{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Payroll',exact:true}).click();
  await page.getByLabel('Payroll employee',{exact:true}).selectOption(fixture.employees.employee);
  await page.getByLabel('Monthly basic (INR)',{exact:true}).fill('20000');
  await page.getByLabel('Monthly gross (INR)',{exact:true}).fill('31000');
  await page.getByLabel('Effective from',{exact:true}).fill('2026-12-01');
  await page.getByLabel('PF enrolled',{exact:true}).check();
  await page.getByLabel('Professional Tax applies',{exact:true}).check();
  await page.getByLabel('Reason for payroll change',{exact:true}).fill('Verified employee payroll profile and enrolment for regression');
  await page.getByRole('button',{name:'Save payroll profile',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Effective payroll profile saved');
  await page.getByLabel('Payroll month',{exact:true}).fill('2026-12');
  await page.getByLabel('Unpaid equivalent days',{exact:true}).fill('1');
  await page.getByRole('button',{name:'Preview calculation',exact:true}).click();
  await expect(page.getByText('Salary reduction: ₹1,000.00',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`output/team-charter-20261125/payroll-${width}.png`,fullPage:true});
  await page.getByRole('button',{name:'Edit guide',exact:true}).click();
  await page.getByLabel('Reporting employee',{exact:true}).selectOption(fixture.employees.employee);
  await page.getByLabel('Designation',{exact:true}).fill('Programme Coordinator');
  await page.getByLabel('Reporting manager',{exact:true}).selectOption(fixture.employees.manager);
  await page.getByLabel('Reason for employee change',{exact:true}).fill('Confirmed programme coordinator and reporting manager for regression');
  await page.getByRole('button',{name:'Save employee reporting',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Employee role and reporting updated');
 });
 test('parental leave reaches HR verification and manager approval',async({page})=>{
  // Release only this suite's fictional requests through the normal audited
  // workflow, so reruns do not consume the five-day parental allowance.
  await login(page,'hr');await page.goto('/volunteering/time-leave?view=team');
  const prior=await call(page,'time_leave_portal.get_time_workspace',{view:'team',employee:fixture.employees.employee});
  for(const row of prior.requests.filter((r:any)=>r.employee===fixture.employees.employee&&r.type==='Paternity Leave'&&r.reason.startsWith('Parental leave charter regression')&&['Open','Approved'].includes(r.status))){
   await call(page,'time_leave_portal.decide_time_request',{doctype:row.doctype,name:row.name,action:row.status==='Approved'?'reverse':'cancel',expected_modified:row.modified,reason:'Retiring this suite’s fictional parental leave before a fresh isolated regression run'});
  }
  await login(page,'employee');await page.goto('/volunteering/time-leave');
  await page.getByRole('button',{name:'New request',exact:true}).click();
  await page.getByLabel('Leave category',{exact:true}).selectOption('Medical');
  await page.getByLabel('Include a half day',{exact:true}).check();
  await page.getByLabel('Request type',{exact:true}).selectOption('Paternity Leave');
  await expect(page.getByLabel('Leave category',{exact:true})).toHaveCount(0);
  await expect(page.getByLabel('Include a half day',{exact:true})).toHaveCount(0);
  await expect(page.getByLabel('Manager informed on',{exact:true})).toHaveCount(0);
  const workspace=await call(page,'time_leave_portal.get_time_workspace');
  const reserved=workspace.requests.filter((row:any)=>['Open','Approved'].includes(row.status));
  const chosen=new Date('2026-12-21T12:00:00');
  while(reserved.some((row:any)=>row.from_date<=chosen.toISOString().slice(0,10)&&(row.to_date||row.from_date)>=chosen.toISOString().slice(0,10))||chosen.getDay()===0)chosen.setDate(chosen.getDate()+1);
  const date=chosen.toISOString().slice(0,10);
  await page.getByLabel('Expected or actual childbirth date',{exact:true}).fill('2026-12-01');
  await page.getByLabel('From date',{exact:true}).fill(date);await page.getByLabel('To date',{exact:true}).fill(date);
  const reason=`Parental leave charter regression ${width} ${Date.now()}`;
  await page.getByLabel('Reason',{exact:true}).fill(reason);await page.getByRole('button',{name:'Submit request',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Request saved');
  await login(page,'hr');await page.goto('/volunteering/time-leave?view=team');
  await page.getByRole('button').filter({hasText:reason}).click();
  await page.getByLabel('HR eligibility verification notes',{exact:true}).fill('Verified childbirth date, employee record and parental entitlement');
  await page.getByRole('button',{name:'Verify parental eligibility',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Eligibility verified');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`output/team-charter-20261125/parental-${width}.png`,fullPage:true});
  await login(page,'manager');await page.goto('/volunteering/time-leave?view=team');
  await page.getByRole('button').filter({hasText:reason}).click();
  await page.getByRole('button',{name:'Approve',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Decision recorded');
 });
 test('medical certificate is attached privately and manager can decide',async({page})=>{
  test.skip(!process.env.E2E_MEDICAL_PDF,'Requires a generated blank medical test PDF.');
  await login(page,'employee');await page.goto('/volunteering/time-leave');
  const workspace=await call(page,'time_leave_portal.get_time_workspace');
  const start=new Date('2026-12-01T12:00:00');
  let end=new Date(start);end.setDate(start.getDate()+3);
  while(workspace.requests.some((r:any)=>['Open','Approved'].includes(r.status)&&r.from_date<=end.toISOString().slice(0,10)&&r.to_date>=start.toISOString().slice(0,10))){start.setDate(start.getDate()+1);end=new Date(start);end.setDate(start.getDate()+3);}
  await page.getByRole('button',{name:'New request',exact:true}).click();
  await page.getByLabel('Request type',{exact:true}).selectOption('Privilege Leave');
  await page.getByLabel('Leave category',{exact:true}).selectOption('Medical');
  await page.getByLabel('From date',{exact:true}).fill(start.toISOString().slice(0,10));
  await page.getByLabel('To date',{exact:true}).fill(end.toISOString().slice(0,10));
  await page.getByLabel('Manager informed on',{exact:true}).fill(workspace.today);
  await page.getByLabel('Private supporting certificate',{exact:true}).setInputFiles(process.env.E2E_MEDICAL_PDF!);
  await expect(page.getByRole('link',{name:'View uploaded certificate',exact:true})).toBeVisible();
  const reason=`Medical certificate charter regression ${width} ${Date.now()}`;
  await page.getByLabel('Reason',{exact:true}).fill(reason);
  await page.getByRole('button',{name:'Submit request',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Request saved');
  await login(page,'manager');await page.goto('/volunteering/time-leave?view=team');
  await page.getByRole('button').filter({hasText:reason}).click();
  const proof=page.getByRole('link',{name:'Open private supporting certificate',exact:true});
  await expect(proof).toBeVisible();expect(await proof.getAttribute('href')).toContain('/private/files/');
  expect((await page.request.get((await proof.getAttribute('href'))!)).ok()).toBeTruthy();
  await page.getByRole('button',{name:'Approve',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Decision recorded');
 });
});
