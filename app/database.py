from time import sleep
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL
from typing import AsyncGenerator

connection_engine = None

while connection_engine is None:
    try:
        connection_engine = create_engine(
            DATABASE_URL, connect_args={}
        )
    except Exception as e:
        print(f'Error occured when trying to connect to database:\n\n{e}')

        print(f'Retrying in 3s...')
        sleep(3)

engine = connection_engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

AsyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session