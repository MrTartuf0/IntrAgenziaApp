import json
import re
import asyncio
from datetime import date, timedelta
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page

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
    """Trova gli URL dei menu per Pascoli."""
    urls = [None, None, None, None] # [OggiLunch, OggiDinner, DomaniLunch, DomaniDinner]
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
    """
    Visita la pagina di un singolo pasto.
    Restituisce: (piatti, prenotato, prenotabile)
    """
    print(f"Parsing menu: {url}")
    await page.goto(url)
    
    # --- LOGICA ROBUSTA BASATA SULLE CLASSI CSS ---
    prenotabile = False
    
    # 1. CHECK PRENOTABILE
    # Cerchiamo il DIV che avvolge il checkbox (identificato dalla classe specifica di Drupal)
    checkbox_wrapper = page.locator(".js-form-item-vuoi-prenotare")
    
    if await checkbox_wrapper.count() > 0:
        # Leggiamo le classi CSS del contenitore come stringa
        classes = await checkbox_wrapper.get_attribute("class") or ""
        
        # DEBUG: Stampiamo le classi trovate per capire cosa vede lo scraper
        # print(f"Classi wrapper checkbox: {classes}")

        # Se tra le classi C'È 'js-webform-states-hidden', il checkbox è nascosto -> NON prenotabile
        if "js-webform-states-hidden" in classes:
            prenotabile = False
        else:
            # Se la classe hidden NON c'è, il checkbox è visibile -> Prenotabile
            prenotabile = True
    else:
        # Se il wrapper del checkbox non esiste proprio, non è prenotabile
        prenotabile = False

    # 2. CHECK GIÀ PRENOTATO
    prenotato = False
    warning_loc = page.locator(".alert.alert-warning")
    # Qui usiamo count() perché l'alert appare/scompare dal DOM, non viene solo nascosto col CSS
    if await warning_loc.count() > 0:
        msg = await warning_loc.text_content()
        if msg and "Risulta già presente una prenotazione" in msg:
            prenotato = True
            prenotabile = False 

    # --- ESTRAZIONE PIATTI ---
    # Nota: Estraiamo tutto ciò che è nel DOM, anche se nascosto, come richiesto.
    grouped = {v: [] for v in CATEGORY_MAP.values()}
    
    # I fieldset contengono le categorie (Primi, Secondi...)
    fieldsets = page.locator("fieldset")
    fs_count = await fieldsets.count()
    
    for i in range(fs_count):
        fs = fieldsets.nth(i)
        
        # Leggiamo la legenda (es. "Primi piatti")
        legend_loc = fs.locator(".fieldset-legend")
        if await legend_loc.count() == 0:
            continue
            
        legend_text = (await legend_loc.text_content()).strip()
        cat_key = CATEGORY_MAP.get(legend_text)
        
        if not cat_key:
            continue
            
        # Troviamo i radio button (i piatti)
        radios = fs.locator("input[type=radio]")
        r_count = await radios.count()
        
        for j in range(r_count):
            radio = radios.nth(j)
            val = await radio.get_attribute("value")
            
            # Scartiamo valori non numerici (es. "STANDARD")
            if not val or not NUMERIC_ID.match(val.strip()):
                continue
                
            # Troviamo il nome del piatto dalla label associata all'ID del radio
            radio_id = await radio.get_attribute("id")
            label_loc = fs.locator(f"label[for='{radio_id}']")
            
            if await label_loc.count() > 0:
                name = (await label_loc.text_content()).strip()
                grouped[cat_key].append({
                    "id": val.strip(),
                    "nome": name
                })
                
    return grouped, prenotato, prenotabile

async def scrape_and_cache_daily():
    print("--- INIZIO SCRAPING GIORNALIERO ---")
    async with async_playwright() as p:
        # Usa headless=True in produzione (senza interfaccia grafica)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # 1. Login
            await login(page)

            # 2. Ottieni URL per oggi e domani
            menu_urls = await get_menu_urls(page)
            # menu_urls struttura: [OggiLunch, OggiDinner, DomaniLunch, DomaniDinner]
            
            today = date.today()
            tomorrow = today + timedelta(days=1)
            
            # Mappiamo gli URL alle date e tipi
            meal_definitions = [
                (today, "pranzo"),
                (today, "cena"),
                (tomorrow, "pranzo"),
                (tomorrow, "cena")
            ]
            
            # Dizionario per raccogliere i dati prima di salvare
            # Chiave: "YYYY-MM-DD", Valore: Lista di pasti
            results = {
                today.isoformat(): [],
                tomorrow.isoformat(): []
            }
            
            for i, url in enumerate(menu_urls):
                day_obj, tipo = meal_definitions[i]
                
                if not url:
                    print(f"Skipping {tipo} del {day_obj}: URL non trovato.")
                    continue
                
                # 3. Parsing
                dishes, prenotato, prenotabile = await parse_menu_page(page, url)
                
                meal_data = {
                    "data": day_obj.isoformat(),
                    "tipo_pasto": tipo,
                    "prenotato": prenotato,
                    "prenotabile": prenotabile,
                    "piatti": dishes
                }
                
                results[day_obj.isoformat()].append(meal_data)
            
            # 4. Salvataggio su Redis
            for day_str, meals in results.items():
                if meals:
                    key = f"menu:{day_str}"
                    await redis_client.set(key, json.dumps(meals))
                    print(f"Salvato menu per {day_str} in Redis (key: {key}, {len(meals)} pasti).")
                else:
                    print(f"Nessun dato trovato per {day_str}.")

        except Exception as e:
            print(f"ERRORE CRITICO DURANTE LO SCRAPING: {e}")
        finally:
            await browser.close()
            print("--- FINE SCRAPING GIORNALIERO ---")

async def get_cached_menu(day: date):
    """Recupera il menu dal database Redis."""
    key = f"menu:{day.isoformat()}"
    raw = await redis_client.get(key)
    if not raw:
        return None
    return json.loads(raw)






async def book_meal(page: Page, meal_url: str, dish_ids: List[str]) -> bool:
    """
    Esegue la prenotazione usando JavaScript diretto e gestendo il caricamento AJAX di Drupal.
    """
    print(f"Inizio prenotazione su: {meal_url}")
    await page.goto(meal_url)
    await page.wait_for_load_state("networkidle")
    
    # 1. Step START: "Vuoi prenotare?"
    try:
        await page.wait_for_selector("#edit-vuoi-prenotare", state="attached")
        
        check_script = """() => {
            var el = document.querySelector('#edit-vuoi-prenotare');
            if (el && !el.checked) {
                el.click();
                return true;
            }
            return false;
        }"""
        was_unchecked = await page.evaluate(check_script)
        if was_unchecked:
            print("Checkbox 'Vuoi prenotare' cliccato (via JS).")
            
    except Exception as e:
        print(f"Errore Checkbox Start: {e}")
        return False

    # Clic su "Procedi >"
    try:
        await page.wait_for_selector("#edit-cards-next", state="attached")
        await page.evaluate("() => document.querySelector('#edit-cards-next').click()")
    except Exception as e:
        print(f"Errore bottone Procedi 1: {e}")
        return False
    
    # 2. Step TIPO MENU: Selezioniamo STANDARD
    await page.wait_for_selector("#edit-tipologia-menu-standard", state="attached")
    await page.evaluate("() => document.querySelector('#edit-tipologia-menu-standard').click()")
    
    # Clic su "Procedi >"
    await page.wait_for_selector("#edit-cards-next", state="attached")
    await page.evaluate("() => document.querySelector('#edit-cards-next').click()")
    
    # 3. Step SELEZIONE PIATTI
    try:
        await page.wait_for_selector("fieldset", state="attached")
        await asyncio.sleep(0.5) 
    except:
        pass

    print(f"Seleziono i piatti: {dish_ids}")
    for dish_id in dish_ids:
        js_script = f"""() => {{
            var el = document.querySelector('input[type="radio"][value="{dish_id}"]');
            if (el) {{
                el.scrollIntoView();
                el.click();
                return true;
            }} else {{
                return false;
            }}
        }}"""
        
        found = await page.evaluate(js_script)
        if found:
            print(f" - Selezionato piatto ID: {dish_id}")
        else:
            print(f" - ATTENZIONE: Piatto ID {dish_id} non trovato nel DOM!")

    # 4. Step ANTEPRIMA (Scatena l'AJAX)
    print("Clicco su Anteprima...")
    await page.wait_for_selector("#edit-actions-preview-next", state="attached")
    await page.evaluate("() => document.querySelector('#edit-actions-preview-next').click()")
    
    # --- GESTIONE AJAX DRUPAL ---
    
    # Dopo aver cliccato Anteprima, il sito fa una chiamata AJAX e inietta il bottone "Invia".
    # Dobbiamo aspettare che l'elemento con value="Invia" compaia nel DOM.
    print("Attendo caricamento AJAX del bottone finale...")
    
    try:
        # Aspettiamo fino a 15 secondi che appaia l'input con value="Invia"
        # Usiamo il selettore CSS preciso per l'input (come visto nel tuo JSON)
        submit_selector = 'input[value="Invia"]'
        await page.wait_for_selector(submit_selector, state="attached", timeout=15000)
        
        # Un piccolo sleep extra per essere sicuri che i listener JS siano attivi
        await asyncio.sleep(1)

        # 5. Step CONFERMA FINALE (Invia)
        print("Bottone Invia trovato! Clicco...")
        
        submit_script = """() => {
            var btn = document.querySelector('input[value="Invia"]');
            if (btn) {
                btn.click();
                return true;
            }
            return false;
        }"""
        clicked = await page.evaluate(submit_script)
        
        if clicked:
            print("Prenotazione INVIATA (Click finale).")
            # Attendiamo che il sito processi l'invio finale
            await page.wait_for_load_state("networkidle")
            
            # Opzionale: Verificare il messaggio di successo finale "Prenotazione effettuata"
            # Ma per ora ci basta sapere che il click è andato.
            return True
        else:
            print("Errore: Impossibile cliccare il pulsante 'Invia'.")
            return False

    except Exception as e:
        print(f"Errore durante l'attesa del bottone Invia (AJAX timeout?): {e}")
        await page.screenshot(path="debug_ajax_fail.png")
        return False
