const { resolve } = require("node:path");
const { pathToFileURL } = require("node:url");
const { writeFile } = require("node:fs/promises");
const { chromium } = require(resolve(__dirname, "../../dashboard/frontend/node_modules/@playwright/test"));

(async () => {
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 1350 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(pathToFileURL(resolve(__dirname, "index.html")).href);
    await page.evaluate(() => document.fonts.ready);
    const checks = await page.evaluate(() => ({
      chapters: document.querySelectorAll("article > h2").length,
      missingImages: [...document.images].filter(image => !image.complete || !image.naturalWidth).map(image => image.alt),
      overflow: document.documentElement.scrollWidth > innerWidth,
      tables: document.querySelectorAll("table").length,
      deadAnchors: [...document.querySelectorAll('a[href^="#"]')].filter(link => !document.getElementById(link.hash.slice(1))).length,
    }));
    if (errors.length || checks.missingImages.length || checks.overflow || checks.deadAnchors || checks.chapters !== 15) {
      throw new Error(JSON.stringify({ errors, checks }));
    }
    await page.screenshot({ path: resolve(__dirname, "preview.png") });
    const pdf = await page.pdf({
      path: resolve(__dirname, "report.pdf"),
      format: "A4", preferCSSPageSize: true, printBackground: true,
      displayHeaderFooter: true, headerTemplate: "<span></span>",
      footerTemplate: '<div style="font:8px Arial;color:#60747c;width:100%;padding:0 17mm;display:flex;justify-content:space-between"><span>IRON WEB · SYSTEM REPORT · 18 OCTOBER 2026</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
      tagged: true, outline: true,
    });
    const validation = { ...checks, browserErrors: errors, pdfBytes: pdf.length, pages: (pdf.toString("latin1").match(/\/Type\s*\/Page\b/g) || []).length };
    await writeFile(resolve(__dirname, "render-checks.json"), JSON.stringify(validation, null, 2) + "\n");
    console.log(JSON.stringify(validation));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
