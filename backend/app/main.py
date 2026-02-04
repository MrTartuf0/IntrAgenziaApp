import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scraper import scrape_and_cache_daily, get_cached_menu
from datetime import date

# Configuriamo lo scheduler
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- ALL'AVVIO ---
    print("Avvio applicazione backend...")
    
    # 1. Avvia lo scheduler
    # Pianifica lo scraping ogni notte all'una (01:00)
    scheduler.add_job(scrape_and_cache_daily, CronTrigger(hour=1, minute=0))
    scheduler.start()
    print("Scheduler avviato (Scraping programmato alle 01:00).")
    
    # 2. Esegui lo scraping immediato in background
    # Usiamo create_task per non bloccare l'avvio del server
    asyncio.create_task(scrape_and_cache_daily())
    
    yield
    
    # --- ALLA CHIUSURA ---
    print("Spegnimento applicazione...")
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

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
    tomorrow = date.today() + date(1970, 1, 2) # Trick rapido o timedelta
    # Meglio usare timedelta
    from datetime import timedelta
    tomorrow = date.today() + timedelta(days=1)
    menu = await get_cached_menu(tomorrow)
    return {"date": tomorrow.isoformat(), "menu": menu}
