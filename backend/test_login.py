import asyncio
import os
from playwright.async_api import async_playwright
from app.settings import settings

# URL definiti nel vecchio scraper
LOGIN_URL = "https://intragenzia.adisu.umbria.it/user/login"

async def test_login():
    async with async_playwright() as p:
        # Avviamo il browser. 
        # headless=False ti permette di vedere il browser aprirsi (utile per debug).
        # Mettilo a True se gira su server/docker.
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Navigazione verso: {LOGIN_URL}")
        await page.goto(LOGIN_URL)

        # Compilazione del form
        # I selettori input[name="..."] sono basati sul vecchio scraper
        print(f"Tentativo di login con utente: {settings.MENU_USERNAME}")
        
        # Aspettiamo che i campi siano visibili
        await page.wait_for_selector('input[name="name"]')
        
        # Inserimento credenziali
        await page.fill('input[name="name"]', settings.MENU_USERNAME)
        await page.fill('input[name="pass"]', settings.MENU_PASSWORD)

        # Click sul pulsante di login (cerca input con id edit-submit o op="Log in")
        # Playwright può cliccare basandosi sul testo o sul selettore CSS
        print("Invio credenziali...")
        await page.click('input[id="edit-submit"], button:has-text("Log in"), input[value="Log in"]')

        # Attendiamo la navigazione dopo il click
        await page.wait_for_load_state("networkidle")

        # Verifica del login
        title = await page.title()
        print(f"Titolo pagina post-login: {title}")

        # Salviamo uno screenshot per verifica visiva
        os.makedirs("debug_screens", exist_ok=True)
        screenshot_path = "debug_screens/login_result.png"
        await page.screenshot(path=screenshot_path)
        print(f"Screenshot salvato in: {screenshot_path}")

        # Controllo di base: se siamo ancora su /user/login probabilmente è fallito
        if "user/login" not in page.url:
            print("✅ LOGIN EFFETTUATO CON SUCCESSO (URL cambiato)")
        else:
            # A volte Drupal rimanda a /user/ID, ma se rimane su login form c'è un errore
            # Cerchiamo messaggi di errore comuni di Drupal
            error_msg = await page.locator(".messages.error").all_text_contents()
            if error_msg:
                print(f"❌ ERRORE LOGIN RILEVATO: {error_msg}")
            else:
                print("⚠️ Attenzione: L'URL è ancora login, verifica lo screenshot.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_login())
