from datetime import date, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scraper import scrape_and_cache_daily, get_cached_menu

app = FastAPI(title="Mensa Pascoli API")

scheduler = AsyncIOScheduler(timezone="Europe/Rome")


@app.on_event("startup")
async def startup_event():
    scheduler.add_job(scrape_and_cache_daily, "cron", hour=1, minute=0)
    scheduler.start()

    # primo scraping all'avvio
    await scrape_and_cache_daily()


@app.get("/menu/today")
async def menu_today():
    data = await get_cached_menu(date.today())
    if not data:
        raise HTTPException(status_code=404, detail="Menu di oggi non disponibile")
    return JSONResponse(content=data)


@app.get("/menu/tomorrow")
async def menu_tomorrow():
    data = await get_cached_menu(date.today() + timedelta(days=1))
    if not data:
        raise HTTPException(status_code=404, detail="Menu di domani non disponibile")
    return JSONResponse(content=data)
