import asyncio
from datetime import date, timedelta
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from playwright.async_api import async_playwright, Browser, Playwright

# Importiamo le funzioni e l'utility di ottimizzazione
from app.scraper import scrape_and_cache_daily, get_cached_menu, book_meal, setup_optimized_page
from app.settings import settings

# --- MODELLI DATI ---
class BookingRequest(BaseModel):
    username: str
    password: str
    meal_url: str
    dish_ids: List[str]

# --- STATO GLOBALE ---
# Qui salviamo l'istanza del browser aperta una volta sola
playwright_instance: Optional[Playwright] = None
global_browser: Optional[Browser] = None

# SEMAFORO: Limitiamo a 5 le prenotazioni contemporanee per non far esplodere la RAM
MAX_CONCURRENT_BOOKINGS = 5
booking_semaphore = asyncio.Semaphore(MAX_CONCURRENT_BOOKINGS)

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global playwright_instance, global_browser
    
    print("--- AVVIO BACKEND ---")
    
    # 1. AVVIAMO IL BROWSER GLOBALE (Singleton)
    print("Avvio Browser Playwright Global...")
    playwright_instance = await async_playwright().start()
    # headless=True per il server
    global_browser = await playwright_instance.chromium.launch(headless=True)
    print("Browser Globale Pronto.")

    # 2. SCHEDULER
    scheduler.add_job(scrape_and_cache_daily, CronTrigger(hour=1, minute=0))
    scheduler.start()
    
    # Eseguiamo uno scraping all'avvio in background
    asyncio.create_task(scrape_and_cache_daily())
    
    yield
    
    # --- SPEGNIMENTO ---
    print("--- SPEGNIMENTO BACKEND ---")
    if global_browser:
        print("Chiusura Browser Globale...")
        await global_browser.close()
    if playwright_instance:
        await playwright_instance.stop()
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

# --- ROTTE ---

@app.get("/")
async def root():
    return {"message": "IntrAgenzia Backend is running (Optimized)"}

@app.get("/menu/today")
async def read_menu_today():
    today = date.today()
    menu = await get_cached_menu(today)
    return {"date": today.isoformat(), "menu": menu}

@app.get("/menu/tomorrow")
async def read_menu_tomorrow():
    tomorrow = date.today() + timedelta(days=1)
    menu = await get_cached_menu(tomorrow)
    return {"date": tomorrow.isoformat(), "menu": menu}

@app.post("/book")
async def make_reservation_endpoint(request: BookingRequest):
    """
    Endpoint ottimizzato: usa il browser globale, blocca immagini e usa un semaforo.
    """
    # Se il browser globale non è partito per qualche motivo, errore grave
    if not global_browser:
        raise HTTPException(status_code=500, detail="Browser service not available")

    # USIAMO IL SEMAFORO: Se ci sono già 5 persone che prenotano, la 6^ aspetta qui.
    async with booking_semaphore:
        print(f"Inizio slot prenotazione per: {request.username}")
        
        # Creiamo un contesto leggero dal browser globale
        context = await global_browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # OTTIMIZZAZIONE: Blocchiamo immagini/font per questa pagina
        await setup_optimized_page(page)
        
        try:
            # 1. Login Inline (usando la pagina ottimizzata)
            print(f"Login per {request.username}...")
            await page.goto("https://intragenzia.adisu.umbria.it/user/login")
            await page.fill('input[name="name"]', request.username)
            await page.fill('input[name="pass"]', request.password)
            
            # Usiamo wait_for_load_state invece di semplice click and pray
            async with page.expect_navigation():
                await page.click('#edit-submit')
            
            # Verifica Login
            if "user/login" in page.url:
                 # Proviamo a vedere se c'è un messaggio d'errore
                 error_msg = "Credenziali non valide"
                 try:
                     div = page.locator(".messages.error")
                     if await div.count() > 0:
                         error_msg = await div.first.text_content()
                 except: pass
                 raise HTTPException(status_code=401, detail=error_msg.strip())

            # 2. Eseguiamo la prenotazione (usa la funzione robusta in scraper.py)
            success = await book_meal(page, request.meal_url, request.dish_ids)
            
            if success:
                return {"status": "success", "message": "Prenotazione effettuata con successo"}
            else:
                raise HTTPException(status_code=500, detail="Errore generico durante la prenotazione")
                
        except HTTPException as he:
            raise he
        except Exception as e:
            print(f"Exception during booking: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # IMPORTANTE: Chiudiamo sempre la pagina/contesto per liberare RAM
            await context.close()
            print(f"Fine slot prenotazione per: {request.username}")
