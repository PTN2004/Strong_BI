const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`[${msg.type()}] ${msg.text()}`);
    }
  });

  page.on('pageerror', error => {
    console.log(`[pageerror] ${error.message}`);
    console.log(error.stack);
  });

  await page.goto('http://localhost:8080/databases', { waitUntil: 'networkidle' }).catch(e => console.log('goto error:', e.message));
  
  await new Promise(resolve => setTimeout(resolve, 3000)); // wait for react to render
  
  await browser.close();
})();
