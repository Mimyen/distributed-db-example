import logging
import os
from fastapi import FastAPI, Request, Response, staticfiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from sqlalchemy import text
from app.database import engine, SessionLocal
from app.domain.model_base import Base
from app.config import CORS_ORIGINS, SECRET_KEY, ENCRYPTION_ALGORITHM, DATABASE_URL
from app.routers import oauth2, router, user
from app.internal import develop
from app.internal.admin import create_admin
from app.domain.token_blacklist.service import get_blacklist_tokens, delete_blacklist_token
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from alembic.config import Config as AlembicConfig
from alembic import command
import datetime

logger = logging.getLogger("\t  Automigrate")
task_logger = logging.getLogger("\t  TaskScheduler")

def remove_expired_blacklisted_tokens():
    task_logger.info(f" Executing periodic task {remove_expired_blacklisted_tokens.__name__}() ...")
    # Add your task logic here
    try:
        with SessionLocal() as db:
            for blacklisted_token in get_blacklist_tokens(db):
                if blacklisted_token.expiration_date < datetime.datetime.now():
                    db.delete(blacklisted_token)
            db.commit()
        task_logger.info(f" Finished running periodic task {remove_expired_blacklisted_tokens.__name__}()")
    except Exception as e:
        task_logger.error(f" Error occured while running perodic task {remove_expired_blacklisted_tokens.__name__}(): {e}")
        

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(remove_expired_blacklisted_tokens, IntervalTrigger(hours=1))
    scheduler.start()
    remove_expired_blacklisted_tokens()
    return scheduler

# Functions
def check_for_changes(alembic_cfg):
    temp_script_path = "app/alembic/versions/temp_rev_id_temporary_migration.py"
    logger.info(" Generating temporary migration script...")

    try:
        # Use the unified logging
        command.revision(
            alembic_cfg,
            autogenerate=True,
            message="Temporary migration",
            rev_id="temp_rev_id"
        )

        # Check for script existence and size
        if os.path.exists(temp_script_path) and os.path.getsize(temp_script_path) > 0:
            logger.info(" Migration script generated. Changes detected.")
            return True
        else:
            logger.info(" No changes detected.")
            return False
    except Exception as e:
        logger.info(f" Error checking for changes: {e}")
        return False

def apply_migrations(alembic_cfg):
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info(" Migrations applied successfully.")
    except Exception as e:
        logger.error(f" Error during migrations: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    alembic_cfg = AlembicConfig("alembic.ini")

    logger.info(" Checking for database changes...")
    if check_for_changes(alembic_cfg):
        logger.info(" Applying migrations...")
        apply_migrations(alembic_cfg)

        with SessionLocal() as db:
            db.execute(text("DROP TABLE IF EXISTS alembic_version;"))
            db.commit()
            try:
                os.remove("app/alembic/versions/temp_rev_id_temporary_migration.py")
            except Exception as e:
                logger.error(e)

    scheduler = start_scheduler()
    try:
        yield
    finally:
        scheduler.shutdown()

def create_db() -> None:
    """
    Function responsible for creating the database.
    """
    Base.metadata.create_all(bind=engine)

def get_application() -> FastAPI:
    """
    Function responsible for preparing the FastAPI application.
    """
    fapp = FastAPI(
        swagger_ui_parameters={"syntaxHighlight.theme": "obsidian"},
        lifespan=lifespan
    )

    create_db()

    fapp.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    fapp.include_router(router)
    fapp.include_router(oauth2.router)
    fapp.include_router(user.router)
    fapp.include_router(develop.router)

    add_pagination(fapp)

    return fapp

app = get_application()

admin = create_admin(app)

app.mount("/media/uploads/user", staticfiles.StaticFiles(directory="app/media/uploads/user"), name="user_uploads")

@app.middleware("http")
async def db_session_middleware(
    request: Request, 
    call_next
) -> Response:
    '''
    The middleware will create a new SQLAlchemy SessionLocal for each request,
    add it to the request, and close it once the request is finished.
    '''
    response = Response("Internal server error", status_code=500)
    response = await call_next(request)

    return response
