"""Iter54: download certificate PDF for long/short-name via Playwright."""
import asyncio, json, sys
from pathlib import Path
from playwright.async_api import async_playwright

STATE = json.loads(Path("/app/test_reports/iteration52_fixture.json").read_text())
BASE = STATE["base_url"].rstrip("/")
OUT = Path("/app/test_reports/pdf_bug_verification3")
OUT.mkdir(parents=True, exist_ok=True)


async def download_cert(name_tag: str):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(accept_downloads=True, viewport={"width":1920,"height":1080})
        page = await ctx.new_page()
        page.on("console", lambda m: print(f"CONSOLE[{m.type}]: {m.text}") if m.type in ("error","warning") else None)

        # Login
        await page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector('input[type="email"]', timeout=15000)
        await page.fill('input[type="email"]', STATE["pastor_email"])
        await page.fill('input[type="password"]', STATE["pastor_password"])
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(3000)
        print("Logged in, url=", page.url)

        # Go to persona 360
        await page.goto(f"{BASE}/personas/{STATE['member_person_id']}", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        print("Persona url=", page.url)
        await page.screenshot(path=str(OUT/f"persona_{name_tag}.png"), full_page=False)

        # Click Carnet y certificado tab
        try:
            await page.get_by_role("tab", name="Carnet y certificado").click(timeout=5000)
        except Exception:
            await page.get_by_text("Carnet y certificado", exact=False).first.click(force=True)
        await page.wait_for_timeout(2000)

        # Click Emitir/Reimprimir certificado
        btn = page.locator('[data-testid="issue-membership-certificate-button"]')
        await btn.wait_for(state="visible", timeout=10000)
        await btn.click(force=True)
        await page.wait_for_timeout(3000)

        # Dialog opens with preview. Wait for QR.
        await page.wait_for_selector('[data-testid="download-membership-document-button"]:not([disabled])', timeout=20000)
        await page.screenshot(path=str(OUT/f"dialog_{name_tag}.png"), full_page=False)

        # Click download
        async with page.expect_download(timeout=30000) as dl_info:
            await page.click('[data-testid="download-membership-document-button"]', force=True)
        dl = await dl_info.value
        dest = OUT / f"cert_{name_tag}.pdf"
        await dl.save_as(str(dest))
        print(f"Saved: {dest}")

        await browser.close()


async def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "long"
    await download_cert(tag)


if __name__ == "__main__":
    asyncio.run(main())
