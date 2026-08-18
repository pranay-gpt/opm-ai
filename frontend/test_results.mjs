import { chromium } from 'playwright';

const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH, headless: true });
const page = await browser.newPage();

page.on('console', msg => {
  console.log('CONSOLE [' + msg.type() + ']:', msg.text());
});
page.on('pageerror', err => console.log('PAGE ERROR:', err.message));
page.on('request', request => {
  if (request.url().includes('plot_group') || request.url().includes('categories')) {
    console.log('REQUEST:', request.method(), request.url());
  }
});
page.on('response', response => {
  if (response.url().includes('plot_group') || response.url().includes('categories')) {
    console.log('RESPONSE:', response.status(), response.url());
  }
});

await page.goto('http://localhost:5173/results');
await page.waitForLoadState('networkidle');
await page.waitForTimeout(2000);

// Click Import Results button
await page.click('button:has-text("Import Results")');
await page.waitForTimeout(1000);

// Select test files
const fileInput = await page.locator('input[type=file]');
await fileInput.setInputFiles([
  '/home/parallels/opm-ai/tests/fixtures/spe1/SPE1CASE1.SMSPEC',
  '/home/parallels/opm-ai/tests/fixtures/spe1/SPE1CASE1.UNSMRY'
]);

// Click Upload button inside dialog
await page.click('dialog button:has-text("Upload")');
await page.waitForTimeout(10000);

// Click Plots tab
await page.click('button:has-text("Plots")');
await page.waitForTimeout(3000);

// Click PROD well CHECKBOX directly (first checkbox)
const prodCheckbox = await page.locator('input[type=checkbox]').first();
await prodCheckbox.click();
await page.waitForTimeout(2000);

// Click Oil Rate checkbox in well rates
const checkboxes = await page.locator('input[type=checkbox]').all();
for (let i = 0; i < checkboxes.length; i++) {
  const label = await checkboxes[i].locator('..').textContent();
  if (label.includes('Oil Rate') && !label.includes('Cumulative')) {
    console.log('\nClicking Oil Rate checkbox', i);
    await checkboxes[i].click();
    await page.waitForTimeout(5000);
    break;
  }
}

// Click Gas Rate checkbox in well rates
const checkboxes2 = await page.locator('input[type=checkbox]').all();
for (let i = 0; i < checkboxes2.length; i++) {
  const label = await checkboxes2[i].locator('..').textContent();
  if (label.includes('Gas Rate') && !label.includes('Cumulative')) {
    console.log('\nClicking Gas Rate checkbox', i);
    await checkboxes2[i].click();
    await page.waitForTimeout(5000);
    break;
  }
}

// Wait for plots
await page.waitForTimeout(3000);

// Test grid layout selector - change to 4col
const gridSelect = await page.locator('select').first();
if (await gridSelect.count() > 0) {
  await gridSelect.selectOption('4col');
  await page.waitForTimeout(1000);
  console.log('\nChanged to 4 columns');
}

// Test per-property checkbox
const perPropertyCheckboxes = await page.locator('input[type=checkbox]').all();
for (let i = 0; i < perPropertyCheckboxes.length; i++) {
  const label = await perPropertyCheckboxes[i].locator('..').textContent();
  if (label.includes('Per-property')) {
    console.log('\nClicking Per-property checkbox', i);
    await perPropertyCheckboxes[i].click();
    await page.waitForTimeout(5000);
    break;
  }
}

// Wait for per-property plots
await page.waitForTimeout(3000);

// Test unit system selector
const unitSelect = await page.locator('select').nth(1);
if (await unitSelect.count() > 0) {
  const options = await unitSelect.locator('option').allTextContents();
  console.log('Unit system options:', options);
  await unitSelect.selectOption('METRIC');
  await page.waitForTimeout(1000);
  console.log('Changed to Metric');
}

// Wait for unit change
await page.waitForTimeout(3000);

// Take final screenshot
await page.screenshot({ path: '/tmp/results_final.png', fullPage: true });
console.log('\nFinal screenshot saved');

await browser.close();
