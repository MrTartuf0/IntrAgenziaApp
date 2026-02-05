import json
import re
import asyncio
from datetime import date, timedelta
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Route

from app.settings import settings
from app.redis_client import redis_client

# --- CONFIGURAZIONE ---
BASE_URL = "https://intragenzia.adisu.umbria.it"
LOGIN_URL = f"{BASE_URL}/user/login"
MENU_TODAY = f"{BASE_URL}/menu-odierni"
MENU_TOMORROW = f"{BASE_URL}/menu-domani"

CATEGORY_MAP = {
    "Primi piatti": "primi_piatti",
    "Secondi piatti": "secondi_piatti",
    "Contorni": "contorni",
    "Frutta": "frutta",
    "Dessert": "dessert",
}

NUMERIC_ID = re.compile(r"^\d+$")

# --- UTILITY PER PERFORMANCE ---
async def block_resources(route: Route):
    """Blocca immagini, font e CSS per velocizzare il caricamento."""
    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()

async def setup_optimized_page(page: Page):
    """Applica il blocco risorse a una pagina."""
    await page.route("**/*", block_resources)


# --- FUNZIONI DI BASE ---

async def login(page: Page):
    """Esegue il login al portale ADISU."""
    print(f"Eseguendo il login per {settings.MENU_USERNAME}...")
    await page.goto(LOGIN_URL)
    
    await page.wait_for_selector('input[name="name"]')
    await page.fill('input[name="name"]', settings.MENU_USERNAME)
    await page.fill('input[name="pass"]', settings.MENU_PASSWORD)
    await page.click('input[id="edit-submit"], button:has-text("Log in"), input[value="Log in"]')
    await page.wait_for_load_state("networkidle")
    print("Login effettuato.")


async def get_menu_urls(page: Page) -> List[Optional[str]]:
    urls = [None, None, None, None] 
    pages_to_check = [(MENU_TODAY, 0), (MENU_TOMORROW, 2)]
    
    for page_url, start_idx in pages_to_check:
        print(f"Cercando link menu in: {page_url}")
        await page.goto(page_url)
        
        links = page.locator("div.view-menu a")
        count = await links.count()
        
        for i in range(count):
            link = links.nth(i)
            text = await link.text_content()
            href = await link.get_attribute("href")
            
            if not text or not href:
                continue

            if "Mensa Pascoli" in text:
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                text_lower = text.lower()
                if "pranzo" in text_lower:
                    urls[start_idx] = full_url
                elif "cena" in text_lower:
                    urls[start_idx + 1] = full_url
                    
    return urls


async def parse_menu_page(page: Page, url: str) -> tuple[Dict, bool, bool]:
    print(f"Parsing menu: {url}")
    await page.goto(url)
    
    prenotabile = False
    checkbox_wrapper = page.locator(".js-form-item-vuoi-prenotare")
    
    if await checkbox_wrapper.count() > 0:
        classes = await checkbox_wrapper.get_attribute("class") or ""
        if "js-webform-states-hidden" in classes:
            prenotabile = False
        else:
            prenotabile = True
    else:
        prenotabile = False

    prenotato = False
    warning_loc = page.locator(".alert.alert-warning")
    if await warning_loc.count() > 0:
        msg = await warning_loc.text_content()
        if msg and "Risulta già presente una prenotazione" in msg:
            prenotato = True
            prenotabile = False 

    grouped = {v: [] for v in CATEGORY_MAP.values()}
    fieldsets = page.locator("fieldset")
    fs_count = await fieldsets.count()
    
    for i in range(fs_count):
        fs = fieldsets.nth(i)
        legend_loc = fs.locator(".fieldset-legend")
        if await legend_loc.count() == 0: continue
            
        legend_text = (await legend_loc.text_content()).strip()
        cat_key = CATEGORY_MAP.get(legend_text)
        if not cat_key: continue
            
        radios = fs.locator("input[type=radio]")
        r_count = await radios.count()
        
        for j in range(r_count):
            radio = radios.nth(j)
            val = await radio.get_attribute("value")
            if not val or not NUMERIC_ID.match(val.strip()): continue
                
            radio_id = await radio.get_attribute("id")
            label_loc = fs.locator(f"label[for='{radio_id}']")
            if await label_loc.count() > 0:
                name = (await label_loc.text_content()).strip()
                grouped[cat_key].append({"id": val.strip(), "nome": name})
                
    return grouped, prenotato, prenotabile


async def book_meal(page: Page, meal_url: str, dish_ids: List[str]) -> bool:
    """Prenotazione con LOGGING AVANZATO, SCREENSHOT e gestione TAB."""
    print(f"\n--- DEBUG START: Prenotazione su {meal_url} ---")
    
    try:
        # 1. Navigazione
        await page.goto(meal_url)
        await page.wait_for_load_state("networkidle")
        print(f"DEBUG: Pagina caricata. URL: {page.url}")
        await page.screenshot(path="debug_1_page_loaded.png")

        # Controllo Login scaduto
        if "user/login" in page.url:
             print("DEBUG: ERRORE - Redirect al login rilevato! Sessione scaduta?")
             return False

        # --- 1-BIS. APERTURA TAB PRENOTAZIONE (FIX UTENTE) ---
        try:
            # Cerchiamo il tab "Prenotazione". Il link ha href="#edit-group-prenotazione"
            # Usiamo un selettore robusto che cerca il link che punta a quel div
            tab_selector = 'a[href="#edit-group-prenotazione"]'
            
            # Verifichiamo se esiste
            if await page.locator(tab_selector).count() > 0:
                print("DEBUG: Tab 'Prenotazione' trovato. Provo a cliccarlo...")
                await page.click(tab_selector)
                # Piccola attesa per l'animazione del tab
                await asyncio.sleep(0.5)
                print("DEBUG: Tab 'Prenotazione' cliccato.")
                await page.screenshot(path="debug_1bis_tab_clicked.png")
            else:
                print("DEBUG: Tab 'Prenotazione' NON trovato. Forse la pagina è già espansa?")
        except Exception as e:
            print(f"DEBUG: Errore non bloccante apertura Tab: {e}")

        # 2. Checkbox "Vuoi prenotare"
        try:
            # Attendiamo che la checkbox diventi visibile (dopo il click sul tab)
            try:
                await page.wait_for_selector("#edit-vuoi-prenotare", state="visible", timeout=3000)
            except:
                print("DEBUG: Checkbox non visibile entro 3s. Provo comunque a cliccarla via JS.")

            # Usiamo JS per cliccare in modo sicuro
            check_script = """() => {
                var el = document.querySelector('#edit-vuoi-prenotare');
                if (el) {
                    if (!el.checked) { el.click(); }
                    return true;
                }
                return false;
            }"""
            if await page.evaluate(check_script):
                print("DEBUG: Checkbox 'Vuoi prenotare' attivata.")
            else:
                 print("DEBUG: Impossibile cliccare la checkbox (JS false).")
                 
                 # Debug extra: dump dei messaggi se fallisce
                 error_msg = await page.locator(".messages.error").all_text_contents()
                 if error_msg:
                     print(f"DEBUG: Messaggi di errore in pagina: {error_msg}")
                 await page.screenshot(path="debug_error_no_checkbox.png")
                 return False

        except Exception as e:
            print(f"DEBUG: Eccezione Checkbox Start: {e}")
            return False

        # Procedi 1
        try:
            await page.wait_for_selector("#edit-cards-next", state="attached", timeout=5000)
            await page.evaluate("() => document.querySelector('#edit-cards-next').click()")
            print("DEBUG: Cliccato 'Procedi' (Step 1).")
        except Exception as e:
            print(f"DEBUG: Errore bottone Procedi 1: {e}")
            await page.screenshot(path="debug_error_procedi1.png")
            return False
    
        # 3. Tipo Menu (Gestione opzionale se c'è solo un menu)
        try:
            await page.wait_for_load_state("networkidle")
            if await page.locator("#edit-tipologia-menu-standard").count() > 0:
                await page.evaluate("() => document.querySelector('#edit-tipologia-menu-standard').click()")
                print("DEBUG: Selezionato 'Menu Standard'.")
                
                await page.wait_for_selector("#edit-cards-next", state="attached", timeout=5000)
                await page.evaluate("() => document.querySelector('#edit-cards-next').click()")
                print("DEBUG: Cliccato 'Procedi' (Step 2).")
            else:
                print("DEBUG: Selezione tipologia menu non trovata (potrebbe essere implicita).")
        except Exception as e:
             print(f"DEBUG: Errore/Skip Step Tipo Menu: {e}")

        # 4. Selezione Piatti
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(1) 
        await page.screenshot(path="debug_2_dish_selection.png")
        
        print(f"DEBUG: ID Piatti richiesti: {dish_ids}")
        
        # --- DIAGNOSTICA PIATTI ---
        visible_radios = page.locator("input[type='radio']")
        count = await visible_radios.count()
        print(f"DEBUG: Trovati {count} radio button totali nella pagina.")
        
        if count == 0:
            print("DEBUG: ERRORE - Nessun piatto trovato!")

        missing_dishes = []
        for dish_id in dish_ids:
            # Selezione JS
            js_script = f"""() => {{
                var el = document.querySelector('input[type="radio"][value="{dish_id}"]');
                if (el) {{ 
                    el.scrollIntoView(); 
                    el.click(); 
                    return true; 
                }}
                return false;
            }}"""
            if await page.evaluate(js_script):
                print(f"DEBUG: ✅ Selezionato piatto {dish_id}")
            else:
                print(f"DEBUG: ⚠️ Trovato ma non cliccabile: {dish_id}")
                missing_dishes.append(dish_id)

        # 5. Anteprima
        print("DEBUG: Tentativo click 'Anteprima'...")
        try:
            await page.wait_for_selector("#edit-actions-preview-next", state="attached", timeout=5000)
            await page.evaluate("() => document.querySelector('#edit-actions-preview-next').click()")
            print("DEBUG: Cliccato 'Anteprima'.")
        except Exception as e:
            print(f"DEBUG: Errore bottone Anteprima: {e}")
            await page.screenshot(path="debug_error_preview.png")
            return False
        
        # 6. Conferma Finale
        print("DEBUG: Attendo caricamento pagina finale (bottone Invia)...")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="debug_3_pre_submit.png")

        submit_selector = 'input[value="Invia"]'
        try:
            await page.wait_for_selector(submit_selector, state="attached", timeout=10000)
        except:
            print("DEBUG: Bottone 'Invia' NON comparso.")
            errors = await page.locator(".messages.error").all_text_contents()
            if errors:
                print(f"DEBUG: Errori di validazione trovati: {errors}")
            return False

        # Click INVIA
        submit_script = """() => {
            var btn = document.querySelector('input[value="Invia"]');
            if (btn) { btn.click(); return true; }
            return false;
        }"""
        
        if await page.evaluate(submit_script):
            print("DEBUG: Cliccato 'Invia'. Attesa conferma...")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3) 
            
            await page.screenshot(path="debug_4_success.png")
            
            if await page.locator(".messages.status").count() > 0:
                 success_msg = await page.locator(".messages.status").first.text_content()
                 print(f"DEBUG: Messaggio di successo: {success_msg}")
            
            print("--- DEBUG END: Successo (apparente) ---")
            return True
        else:
            print("DEBUG: Errore JS nel click 'Invia'.")
            return False
            
    except Exception as e:
        print(f"DEBUG: ECCEZIONE GENERALE BOOK_MEAL: {e}")
        import traceback
        traceback.print_exc()
        await page.screenshot(path="debug_exception_crash.png")
        return False



async def scrape_and_cache_daily():
    print("--- INIZIO SCRAPING GIORNALIERO ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Usiamo user agent reale
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # OTTIMIZZAZIONE: Blocchiamo le risorse anche qui
        await setup_optimized_page(page)
        
        try:
            await login(page)
            menu_urls = await get_menu_urls(page)
            
            today = date.today()
            tomorrow = today + timedelta(days=1)
            
            meal_definitions = [
                (today, "pranzo"), (today, "cena"),
                (tomorrow, "pranzo"), (tomorrow, "cena")
            ]
            
            results = {today.isoformat(): [], tomorrow.isoformat(): []}
            
            for i, url in enumerate(menu_urls):
                day_obj, tipo = meal_definitions[i]
                if not url: continue
                
                dishes, prenotato, prenotabile = await parse_menu_page(page, url)
                
                meal_data = {
                    "data": day_obj.isoformat(),
                    "tipo_pasto": tipo,
                    "prenotato": prenotato,
                    "prenotabile": prenotabile,
                    "piatti": dishes
                }
                results[day_obj.isoformat()].append(meal_data)
            
            for day_str, meals in results.items():
                if meals:
                    key = f"menu:{day_str}"
                    await redis_client.set(key, json.dumps(meals))
                    print(f"Salvato menu per {day_str} ({len(meals)} pasti).")
                else:
                    print(f"Nessun dato per {day_str}.")

        except Exception as e:
            print(f"ERRORE CRITICO SCRAPING: {e}")
        finally:
            await browser.close()
            print("--- FINE SCRAPING GIORNALIERO ---")

async def get_cached_menu(day: date):
    key = f"menu:{day.isoformat()}"
    raw = await redis_client.get(key)
    if not raw: return None
    return json.loads(raw)
