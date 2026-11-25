import { expect, test, type Page } from '@playwright/test';
import { loginViaAPI } from '../../helpers/auth';
import { PERSONAS } from '../../helpers/personas';
import { portalCall, qaReceipt, requireLocalRegression } from '../../helpers/portal-regression';
const API = 'volunteering.volunteering.expense_claim_portal.';
const SUBMIT = '**/api/method/' + API + 'submit_expense_claim';
const STATUS = '**/api/method/volunteering.volunteering.expense_claim_requests.get_expense_submission_status';
async function fillClaim(page: Page, suffix: string) {
  await page.goto('/volunteering/expense-claim');
  const options = await portalCall(page, API + 'get_expense_claim_form');
  await page.getByRole('combobox', { name: 'Project *', exact: true }).selectOption(options.projects[0].value);
  await page.getByRole('combobox', { name: 'Project expense category *', exact: true }).click();
  await page.getByRole('listbox', { name: 'Project expense category *', exact: true }).getByRole('option').first().click();
  await page.getByLabel('Supplier / payee').fill('QA ONLY Training Supplier');
  await page.getByLabel('Receipt / invoice number').fill(suffix);
  await page.getByLabel('Description and business purpose *').fill('QA ONLY: claim safety test ' + suffix);
  await page.getByLabel(/Amount \(/).fill('88');
  await page.getByLabel('Receipt evidence *').setInputFiles(qaReceipt('QA ONLY claim retry receipt ' + suffix));
}
test.beforeEach(async ({page,baseURL}) => { requireLocalRegression(baseURL); await loginViaAPI(page.request,PERSONAS.employee.email,PERSONAS.employee.password); });

test('lost success confirmation recovers one claim and shows pending approval labels',async({page})=>{
  const tag='lost-response-'+Date.now();await fillClaim(page,tag);
  let posts=0;
  await page.route(SUBMIT,async route=>{posts++;const response=await route.fetch();expect(response.status(),await response.text()).toBe(200);await route.abort('connectionfailed');});
  await page.getByRole('button',{name:'Submit for receipt review',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Sent for receipt review',exact:true})).toBeVisible();
  expect(posts).toBe(1);
  const claims=await portalCall(page,API+'get_my_expense_claims');
  const created=claims.claims.filter((row:any)=>row.purpose.includes(tag));expect(created).toHaveLength(1);
  await page.getByRole('link',{name:'Track this claim'}).click();
  await expect(page.getByText('Awaiting approval',{exact:true})).toHaveCount(2);
  await expect(page.getByRole('button',{name:'Withdraw claim',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Withdraw claim',exact:true}).click();
  await page.getByLabel('Withdrawal reason').fill('QA ONLY duplicate cancellation check');
  await page.getByRole('button',{name:'Confirm withdrawal',exact:true}).click();
  await expect(page.getByText('Withdrawn: QA ONLY duplicate cancellation check',{exact:true})).toBeVisible();
  const closed=await portalCall(page,API+'get_my_expense_claim',{name:created[0].name});
  expect(closed.stage).toBe('Withdrawn');expect(closed.can_withdraw).toBe(false);expect(closed.outstanding_amount).toBe(0);
});

test('unconfirmed request and receipts survive refresh; retry checks before resending',async({page})=>{
  const tag='reload-retry-'+Date.now();await fillClaim(page,tag);
  let posts=0;await page.route(SUBMIT,route=>{posts++;return route.abort('connectionfailed');});
  await page.route(STATUS,route=>route.abort('connectionfailed'));
  await page.getByRole('button',{name:'Submit for receipt review',exact:true}).click();
  await expect(page.getByRole('button',{name:'Retry saved submission',exact:true})).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Description and business purpose *')).toHaveValue('QA ONLY: claim safety test '+tag);
  await expect(page.getByText('Ready to upload privately:',{exact:false})).toBeVisible();
  await page.unroute(SUBMIT);await page.unroute(STATUS);
  await page.getByRole('button',{name:'Retry saved submission',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Sent for receipt review',exact:true})).toBeVisible();
  const claims=await portalCall(page,API+'get_my_expense_claims');expect(claims.claims.filter((row:any)=>row.purpose.includes(tag))).toHaveLength(1);expect(posts).toBe(1);
});

test('concurrent requests with one reference create one claim and one receipt',async({page})=>{
  await page.goto('/volunteering/expense-claim');
  const defaults=await portalCall(page,API+'get_expense_claim_form');const project=defaults.projects[0].value;
  const accounts=await portalCall(page,API+'get_project_accounts',{project});
  const receipt=qaReceipt('QA ONLY concurrent submission');
  const payload={project,reimbursement_source:'PERSONAL',expenses:[{account:accounts[0].value,expense_date:defaults.expense_date,description:'QA ONLY concurrent request '+Date.now(),amount:12,receipt_filename:receipt.name,receipt_content:receipt.buffer.toString('base64')}]};
  const key=crypto.randomUUID();
  const results=await page.evaluate(async({method,payload,key})=>{
    const send=async()=>{const response=await fetch('/api/method/'+method,{method:'POST',headers:{'Content-Type':'application/json','X-Frappe-CSRF-Token':(window as any).csrf_token||''},body:JSON.stringify({payload,request_key:key})});if(!response.ok)throw new Error(await response.text());return(await response.json()).message;};
    return Promise.all([send(),send()]);
  },{method:API+'submit_expense_claim',payload,key});
  expect(results[0].name).toBe(results[1].name);
  const history=await portalCall(page,API+'get_my_expense_claims');
  expect(history.claims.filter((row:any)=>row.purpose===payload.expenses[0].description)).toHaveLength(1);
});

test('concurrent independent submissions both survive a database snapshot conflict',async({page})=>{
  await page.goto('/volunteering/expense-claim');
  const defaults=await portalCall(page,API+'get_expense_claim_form');const project=defaults.projects[0].value;
  const accounts=await portalCall(page,API+'get_project_accounts',{project});const tag='independent-'+Date.now();
  const receipt=qaReceipt('QA ONLY independent claims');
  const payload={project,reimbursement_source:'PERSONAL',expenses:[{account:accounts[0].value,expense_date:defaults.expense_date,description:'QA ONLY '+tag,amount:13,receipt_filename:receipt.name,receipt_content:receipt.buffer.toString('base64')}]};
  const keys=[crypto.randomUUID(),crypto.randomUUID()];
  const results=await page.evaluate(async({method,payload,keys})=>Promise.all(keys.map(async key=>{
    const response=await fetch('/api/method/'+method,{method:'POST',headers:{'Content-Type':'application/json','X-Frappe-CSRF-Token':(window as any).csrf_token||''},body:JSON.stringify({payload,request_key:key})});
    if(!response.ok)throw new Error(await response.text());return(await response.json()).message;
  })),{method:API+'submit_expense_claim',payload,keys});
  expect(new Set(results.map((row:any)=>row.name)).size).toBe(2);
  const history=await portalCall(page,API+'get_my_expense_claims');
  expect(history.claims.filter((row:any)=>row.purpose==='QA ONLY '+tag)).toHaveLength(2);
});
