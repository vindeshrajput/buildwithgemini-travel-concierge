const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  if (!fs.existsSync('demo_video')) {
    fs.mkdirSync('demo_video');
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    recordVideo: { dir: 'demo_video/', size: { width: 1280, height: 720 } },
    viewport: { width: 1280, height: 720 }
  });

  const page = await context.newPage();
  console.log('Navigating to Travel Concierge web app...');
  await page.goto('https://travel-concierge-frontend-94300225157.us-east1.run.app');
  await page.waitForTimeout(3000);

  console.log('Clicking 🏖️ Tropical beaches prompt chip...');
  const chips = await page.$$('.prompt-chip');
  if (chips.length > 0) {
    await chips[0].click();
    await page.waitForTimeout(8000);
    await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
    await page.waitForTimeout(2000);
  }

  console.log('Sending Tokyo budget calculation prompt...');
  await page.fill('#input', 'Calculate budget for 5 days in Tokyo');
  await page.waitForTimeout(1000);
  await page.click('.send-btn');
  await page.waitForTimeout(8000);
  await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
  await page.waitForTimeout(2000);

  console.log('Sending Paris postcard image generation prompt...');
  await page.fill('#input', 'Generate a postcard image of Paris');
  await page.waitForTimeout(1000);
  await page.click('.send-btn');
  await page.waitForTimeout(10000);
  await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
  await page.waitForTimeout(4000);

  const video = page.video();
  await context.close();
  await browser.close();
  if (video) {
    const videoPath = await video.path();
    console.log('RECORDED_VIDEO_PATH:', videoPath);
  }
})();
