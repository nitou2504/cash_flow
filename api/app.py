from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from cashflow.config import DB_PATH
from cashflow.database import create_connection, create_tables
from cashflow import controller
from api.auth import router as auth_router
from api.routers.dashboard import router as dashboard_router
from api.routers.transactions import router as transactions_router
from api.routers.accounts import router as accounts_router
from api.routers.categories import router as categories_router
from api.routers.budgets import router as budgets_router
from api.routers.subscriptions import router as subscriptions_router
from api.routers.review import router as review_router
from api.routers.invoices import router as invoices_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = create_connection(DB_PATH)
    create_tables(conn)
    controller.run_monthly_rollover(conn, date.today())
    conn.close()
    yield


app = FastAPI(title="Cash Flow API", version="1.0.0", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(transactions_router)
app.include_router(accounts_router)
app.include_router(categories_router)
app.include_router(budgets_router)
app.include_router(subscriptions_router)
app.include_router(review_router)
app.include_router(invoices_router)

static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        file = static_dir / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(static_dir / "index.html")
