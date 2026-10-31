import {test,expect} from '@playwright/test';

const API='http://127.0.0.1:8000/api';

test('empty store shows onboarding, demo load scores stored records',async({page,request})=>{
  const before=await (await request.get(`${API}/dashboard/summary`)).json();
  test.skip(Object.values(before.records_processed as Record<string,number>).some(Boolean),'backend already holds records (reused server)');
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'No records stored yet'})).toBeVisible();
  await page.locator('.onboarding').getByRole('button',{name:'Load demo dataset'}).click();
  await expect(page.getByRole('status')).toContainText('Demo dataset stored');
  await expect(page.getByRole('heading',{name:'No records stored yet'})).not.toBeVisible();
  await expect(page.locator('tbody tr').first()).toBeVisible();
});

test.describe('with stored demo data',()=>{
  test.beforeAll(async({request})=>{expect((await request.post(`${API}/demo/load`)).ok()).toBeTruthy();expect((await request.post(`${API}/detect/run`)).ok()).toBeTruthy()});

  test('real detector overview, filters, evidence and presentation',async({page})=>{
    const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('/');
    await expect(page.locator('.brand')).toContainText('FinShield');
    await expect(page.getByRole('heading',{name:'See the signals. Find the story.'})).toBeVisible();
    await expect(page.locator('tbody tr').first()).toBeVisible();
    await page.locator('.source-note summary').click();
    await expect(page.locator('.source-note')).toContainText('Showing stored detection run');
    await page.screenshot({path:'test-results/overview.png',fullPage:true});
    await page.getByLabel('Risk level',{exact:true}).selectOption('Low');
    await page.getByRole('button',{name:'Apply',exact:true}).click();
    await expect(page.locator('tbody .badge').first()).toHaveText('Low');
    expect(await page.locator('tbody .badge').allTextContents()).not.toContain('High');
    await page.getByRole('button',{name:'Clear filters'}).click();
    await expect(page.locator('tbody .badge').first()).toHaveText('High');
    await page.locator('tbody .text-link').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.locator('.factor').first().click();
    await expect(page.getByRole('heading',{name:'Selected evidence'})).toBeVisible();
    await page.screenshot({path:'test-results/evidence.png'});
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
    await page.setViewportSize({width:850,height:1000});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    expect(errors).toEqual([]);
  });

  test('loan-to-mule result shows the explicit money flow',async({page})=>{
    await page.goto('/');
    await page.getByPlaceholder('e.g. LG-02').fill('AP-03');
    await page.getByRole('button',{name:'Apply',exact:true}).click();
    // Wait for the filtered result, not the previous table, before opening it.
    await expect(page.locator('tbody tr').first()).toContainText('AP-03');
    await page.locator('tbody .text-link').first().click();
    const flow=page.getByRole('region',{name:'Loan-to-mule money flow'});
    await expect(flow).toBeVisible();
    await expect(flow).toContainText('Disbursement');
    await expect(flow.locator('li.out em').last()).toContainText('% of loan moved');
    await flow.scrollIntoViewIfNeeded();
    await page.screenshot({path:'test-results/loan-flow.png'});
  });

  test('real alert opens its case; decisions persist across reload with the original alert unchanged',async({page})=>{
    await page.goto('/');
    await expect(page.locator('tbody .badge').first()).toHaveText('High');
    await page.locator('tbody .text-link').first().click();
    const dialog=page.getByRole('dialog');
    await dialog.getByRole('button',{name:'Open linked case'}).click();
    await expect(dialog.getByText('CASE WORKSPACE')).toBeVisible();
    const caseId=(await dialog.locator('header h2').textContent())!.trim();
    const score=(await dialog.locator('.score-head h2').textContent())!.trim();
    for(const status of ['Requires Investigation','False Positive']){
      await dialog.getByLabel('Rationale (required)').fill(`Evidence reviewed: ${status}`);
      await dialog.getByRole('button',{name:status,exact:true}).click();
      await expect(dialog.getByText('Decision saved and verified',{exact:false})).toBeVisible();
      await expect(dialog.getByText('Current status:')).toContainText(status);
    }
    await expect(dialog.locator('.history')).toHaveCount(3);
    await page.screenshot({path:'test-results/case.png'});
    await page.reload();
    await page.getByRole('button',{name:'Cases',exact:true}).click();
    await page.getByLabel('Case status').selectOption('False Positive');
    await page.getByRole('button',{name:caseId,exact:true}).click();
    await expect(dialog.getByText('Current status:')).toContainText('False Positive');
    await expect(dialog.locator('.history')).toHaveCount(3);
    await expect(dialog.locator('.history').last()).toContainText('Evidence reviewed: False Positive');
    await expect(dialog.locator('.score-head h2').first()).toHaveText(score);
  });

  test('a failed save is reported and keeps the rationale',async({page})=>{
    await page.route('**/api/cases/*/decision',route=>route.fulfill({status:500,json:{detail:'database unavailable'}}));
    await page.goto('/');
    await page.getByRole('button',{name:'Cases',exact:true}).click();
    await page.locator('tbody .text-link').first().click();
    const dialog=page.getByRole('dialog');
    await dialog.getByLabel('Rationale (required)').fill('Check source records with customer.');
    await dialog.getByRole('button',{name:'Requires Investigation',exact:true}).click();
    await expect(dialog.getByText('database unavailable')).toBeVisible();
    await expect(dialog.getByText('Decision saved')).not.toBeVisible();
    await expect(dialog.getByLabel('Rationale (required)')).toHaveValue('Check source records with customer.');
  });

  test('mixed-format upload stores clean rows, reports dirty ones, and case saves are verified',async({page})=>{
    const run=Date.now();
    const csv=`txn_id,sender_account,timestamp,amount,beneficiary_account\nT-E2E-${run}-1,A-C001,2026-10-30T10:00:00Z,"1,250.00",B-E2E\nT-E2E-${run}-2,A-C001,not-a-date,-5,B-E2E\n`;
    const json=JSON.stringify({customers:[{CustID:`C-E2E-${run}`,FullName:'Test Customer',City:'Pune'}]});
    await page.goto('/');
    await page.getByRole('button',{name:'Data sources',exact:true}).click();
    await page.getByLabel('Choose source files').setInputFiles([
      {name:`payments-${run}.csv`,mimeType:'text/csv',buffer:Buffer.from(csv)},
      {name:`customers-${run}.json`,mimeType:'application/json',buffer:Buffer.from(json)},
    ]);
    await page.getByRole('button',{name:'Upload 2',exact:true}).click();
    await expect(page.getByRole('status')).toContainText('2 file(s) imported');
    const csvReport=page.locator('.report',{hasText:`payments-${run}.csv`});
    await expect(csvReport.locator('.count-accepted b')).toHaveText('1');
    await expect(csvReport.locator('.count-rejected b')).toHaveText('1');
    await expect(csvReport.locator('.severity.error').first()).toBeVisible();
    await expect(page.locator('.report',{hasText:`customers-${run}.json`}).locator('.count-accepted b')).toHaveText('1');
    const row=page.locator('tr',{hasText:`payments-${run}.csv`});
    await row.getByRole('button',{name:'Rejected rows'}).click();
    await expect(page.locator('.evidence-focus')).toContainText(`T-E2E-${run}-2`);
    await expect(page.locator('.evidence-focus')).toContainText('timestamp');
    await page.screenshot({path:'test-results/upload.png',fullPage:true});
    await page.reload();
    await page.getByRole('button',{name:'Data sources',exact:true}).click();
    await expect(page.locator('tr',{hasText:`payments-${run}.csv`})).toBeVisible();
    await page.getByRole('button',{name:'Overview',exact:true}).click();
    await expect(page.locator('.stale')).toBeVisible();
    await page.getByRole('button',{name:'Score latest records'}).click();
    await expect(page.locator('.stale')).not.toBeVisible();
    await expect(page.getByRole('status').first()).toContainText('Detection run');
  });
});
