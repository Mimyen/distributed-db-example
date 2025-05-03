from typing import Annotated, Literal, Optional
from fastapi import APIRouter, Depends, Response, Form, HTTPException, Path, Body, Query, status, File, UploadFile
from sqlalchemy.orm import Session
from app.dependencies import DefaultResponseModel, Authorize, DBSessionProvider, validate_password, CreateExampleResponse, Example, DefaultErrorModel, Responses, CreateAuthResponses, CreateAuthorizeResponses, CreateInternalErrorResponse
from app.config import SECRET_KEY, ENCRYPTION_ALGORITHM, IP_ADDRESS, IMAGE_DIR, IMAGE_URL
from app.domain.user.service import ( 
    get_user_by_email, create_user, get_user
)
from app.domain.user.schemas import UserCreate, User
from pydantic import BaseModel, Field
from uuid import uuid4
import jwt
import re
from fastapi_pagination import Page, paginate

router = APIRouter(
    prefix="/user",
    tags=["User"],
    responses=Responses(
        CreateInternalErrorResponse()
    )
)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED, 
    responses=Responses(
        CreateExampleResponse(
            code=201, 
            description="Successful Response", 
            content_type="application/json", 
            examples=[
                Example(name="User registered", summary="User registered", description="Returned upon successful creation of user from provided data", value=DefaultResponseModel(message="User registed")), 
            ]
        ),
        CreateExampleResponse(
            code=400, 
            description="Bad Request", 
            content_type="application/json", 
            examples=[
                Example(name="Email already in use", summary="Email already in use", description="Email provided in body is already being used", value=DefaultErrorModel(detail="Account with this email already exists")), 
            ]
        ),
    )
)
async def register_user(
    response: Response,
    body: Annotated[UserCreate, Body()], 
    db: Annotated[Session, Depends(DBSessionProvider)]
) -> DefaultResponseModel:
    
    validate_password(body.password)

    if get_user_by_email(db, body.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account with this email already exists"
        )
    
    try:
        create_user(db, body)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while creating the use: {e}"
        )

    return {
        "message": "User registered"
    }

@router.get(
    "/get", 
    status_code=status.HTTP_200_OK,
    responses=Responses(
        CreateExampleResponse(
            code=200, 
            description="Successful Response", 
            content_type="application/json", 
            examples=[
                Example(name="User", summary="User", description="Entire user object", value=User(email="pawel@ochal.ola", id=69, is_active=True)),
            ]
        ),
        CreateAuthorizeResponses(),
        CreateExampleResponse(
            code=404,
            description='Not Found',
            examples=[
                Example(name="User Not Found", summary="User Not Found", description="User with this id doesn't exist", value=DefaultErrorModel(detail="User not found"))
            ]
        )
    )
)
async def get_me(
    response: Response,
    user_id: Annotated[int, Depends(Authorize)],
    db: Annotated[Session, Depends(DBSessionProvider)]
) -> User:
    
    if not (user := get_user(db, user_id)):
        raise HTTPException(
            status_code=404, 
            detail="User not found"
        )
    
    return user