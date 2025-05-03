from typing import Annotated, Literal, Optional, Union
from sqlalchemy import inspect, text, MetaData, select
from typing_extensions import Doc
from fastapi import APIRouter, Depends, Response, Form, HTTPException, Path, Body, Query, status, File, UploadFile
from sqlalchemy.orm import Session
from app.domain.user.models import User
from app.dependencies import DefaultResponseModel, Authorize, DBSessionProvider, validate_password
from app.config import SECRET_KEY, ENCRYPTION_ALGORITHM, IP_ADDRESS, IMAGE_DIR, IMAGE_URL
from app.database import engine
from pydantic import BaseModel
from uuid import uuid4
import subprocess

router = APIRouter(
    prefix="/develop",
    tags=["Develop"],
    responses={404: {'description': 'Not found'}, 500: {'description': 'Internal Server Error'}},
)

@router.post("/create-revision", status_code=status.HTTP_200_OK, deprecated=True)
async def create_new_revision(
    response: Response,
    form: Annotated[Optional[str], Form()] = None
) -> DefaultResponseModel:
    try:
        if not form: result = subprocess.run(f"alembic revision --autogenerate", shell=True, check=True)
        else: result = subprocess.run(f"alembic revision --autogenerate -m \"{form}\"", shell=True, check=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error while migrating: {e}'
        )

    print(result.stdout)

    return {
        "message": "Revision created: {}"
    }

@router.post("/upgrade", status_code=status.HTTP_200_OK, deprecated=True)
async def migrate_database(
    response: Response,
) -> DefaultResponseModel:
    try:
        subprocess.run("alembic upgrade head", shell=True, check=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error while migrating: {e}'
        )

    return {
        "message": "Migrated"
    }

@router.post("/checkout-tables", status_code=status.HTTP_200_OK)
async def checkout_table(
    response: Response,
    db: Annotated[Session, Depends(DBSessionProvider)]
):
    output = {}
    
    inspector = inspect(engine)

    tables = inspector.get_table_names()

    # Iterate over each table and print its columns
    for table in tables:
        # print(f"Table: {table}")
        
        # Get columns for the current table
        columns = inspector.get_columns(table)
        cols = []
        # Print column names and their types
        for column in columns:
            # print(f"Column: {column['name']}, Type: {column['type']}")
            cols.append({
                'Column': f'{column['name']}',
                'Type': f'{column['type']}',
            })
        
        # print("-" * 40)

        output.update({f'{table}': cols})
        

    # print(output)

    return {
        'table': output
    }

@router.post("/reset", status_code=status.HTTP_200_OK, deprecated=True)
async def reset_alembic(
    response: Response,
    db: Annotated[Session, Depends(DBSessionProvider)]
) -> DefaultResponseModel:
    try:
        db.execute(text("DROP TABLE IF EXISTS alembic_version;"))
        db.commit()
        subprocess.run("rm app/alembic/versions/*.py", shell=True, check=True)
        subprocess.run("alembic revision --autogenerate -m \"Initial migration\"", shell=True, check=True)
        subprocess.run("alembic upgrade head", shell=True, check=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error while reseting and creating initial migration: {e}'
        )

    return {
        "message": "Migrated"
    }

@router.get("/revision", status_code=status.HTTP_200_OK, deprecated=True)
async def get_current_revision(
    response: Response,
    db: Annotated[Session, Depends(DBSessionProvider)]
):
    metadata = MetaData()
    metadata.reflect(bind=db.get_bind())  # Get bind from the session

    # Access the alembic_version table
    table_name = 'alembic_version'
    table = metadata.tables.get(table_name)

    if table is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"error": f"Table '{table_name}' not found in the database."}

    # Create and execute the query
    stmt = select(table)
    result = db.execute(stmt)
    rows = result.fetchall()

    # Convert rows to a list of dictionaries
    columns = table.columns.keys()
    result_list = [dict(zip(columns, row)) for row in rows]

    return result_list

@router.delete("/revision", status_code=status.HTTP_200_OK, deprecated=True)
async def delete_revision_table(
    response: Response,
    db: Annotated[Session, Depends(DBSessionProvider)]
) -> DefaultResponseModel:
    db.execute(text("DROP TABLE IF EXISTS alembic_version;"))
    db.commit()

    return {
        "message": "Deleted"
    }

# @router.post("/delete-old-revisions", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_old_revisions(
#     response: Response,
#     db: Annotated[Session, Depends(DBSessionProvider)]
# ) -> DefaultResponseModel:
#     try:
#         subprocess.run("rm app/alembic/versions/*.py", shell=True, check=True)
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f'Error while migrating: {e}'
#         )

#     return {
#         "message": "Migrated"
#     }

@router.post("/run-sql")
async def run_sql_script(
    query: Annotated[str, Form()],
    db: Annotated[Session, Depends(DBSessionProvider)]
):

    result = db.execute(text(f"{query}"))
    db.commit()

    return {"result": result}