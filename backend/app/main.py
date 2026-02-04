import asyncio
from datetime import date, timedelta
from typing import List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from playwright.async_api import async_playwright

# Importa le nuove funzioni
from app.scraper import scrape_and_cache_daily, get_cached_menu, book_meal, login
from app.settings import settings

# --- MODELLI DATI ---
class BookingRequest(BaseModel):
    username: str
    password: str
    meal_url: str  # L'URL completo del pasto (es. https://.../node/3930...)
    dish_ids: List[str] # Lista degli ID dei piatti (es. ["3930259873", "3930259901"])

# --- SETUP SCHEDULER (Invariato) ---
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Avvio applicazione backend...")
    scheduler.add_job(scrape_and_cache_daily, CronTrigger(hour=1, minute=0))
    scheduler.start()
    asyncio.create_task(scrape_and_cache_daily())
    yield
    print("Spegnimento applicazione...")
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

# --- ROTTE ---

@app.get("/")
async def root():
    return {"message": "IntrAgenzia Backend is running"}

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

# NUOVA ROTTA DI PRENOTAZIONE
@app.post("/book")
async def make_reservation_endpoint(request: BookingRequest):
    """
    Endpoint per effettuare una prenotazione reale.
    """
    print(f"Ricevuta richiesta prenotazione per utente: {request.username}")
    
    async with async_playwright() as p:
        # Avviamo il browser (Headless=True in produzione)
        browser = await p.chromium.launch(headless=True)
        # Usiamo user agent reale per evitare blocchi
        context = await browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # 1. Login con le credenziali fornite dall'utente (NON quelle del file .env)
            # Dobbiamo adattare la funzione login per accettare credenziali dinamiche
            # Per ora facciamo login manuale qui o modifichiamo la funzione login.
            # Facciamolo inline per semplicità:
            print(f"Login per {request.username}...")
            await page.goto("https://intragenzia.adisu.umbria.it/user/login")
            await page.fill('input[name="name"]', request.username)
            await page.fill('input[name="pass"]', request.password)
            await page.click('#edit-submit')
            await page.wait_for_load_state("networkidle")
            
            # Verifica Login
            if "user/login" in page.url:
                 raise HTTPException(status_code=401, detail="Credenziali ADISU non valide")

            # 2. Eseguiamo la prenotazione
            success = await book_meal(page, request.meal_url, request.dish_ids)
            
            if success:
                return {"status": "success", "message": "Prenotazione effettuata con successo"}
            else:
                raise HTTPException(status_code=500, detail="Errore durante la compilazione del form")
                
        except Exception as e:
            print(f"Errore prenotazione: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            await browser.close()
