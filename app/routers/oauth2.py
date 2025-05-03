from typing import Annotated
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session
from app.dependencies import CreateExampleResponse, CreateRefreshResponses, DBSessionProvider, Example, ValidateCredentials, Tokens, EncodedTokens, retrieve_refresh_token, create_token, RefreshToken, DefaultResponseModel, Responses, CreateInternalErrorResponse, CreateAuthResponses
from app.config import ACCESS_TOKEN_EXPIRE_TIME, ENCRYPTION_ALGORITHM, REFRESH_TOKEN_EXPIRE_TIME, SECRET_KEY
from app.domain.token_blacklist.service import create_blacklist_token, get_blacklist_token
from app.domain.token_blacklist.schemas import BlacklistTokenElement, BlacklistTokenElementFull
import datetime
import jwt

router = APIRouter(
    prefix="/oauth2",
    tags=["Auth"],
    responses=Responses(
        CreateInternalErrorResponse()
    ),
)


@router.post(
    "/token", 
    status_code=status.HTTP_201_CREATED,
    responses=Responses(
        CreateExampleResponse(
            code=201, 
            description="Successful Response", 
            content_type="application/json", 
            examples=[
                Example(name="Authenticated", summary="Authenticated", value=DefaultResponseModel(message="Authenticated")), 
            ]
        ),
        CreateAuthResponses()
    )
)
async def login_for_access_token(
    response: Response,
    tokens: Annotated[EncodedTokens, Depends(ValidateCredentials)]
) -> DefaultResponseModel:

    response.set_cookie(key="access_token", value=f'{tokens.access_token}', max_age=ACCESS_TOKEN_EXPIRE_TIME * 60, httponly=True)
    response.set_cookie(key="refresh_token", value=f'{tokens.refresh_token}', max_age=REFRESH_TOKEN_EXPIRE_TIME * 60 * 60 * 24, httponly=True)

    return DefaultResponseModel(message="Authenticated")


@router.delete(
    "/token",
    status_code=status.HTTP_200_OK,
    responses=Responses(
        CreateExampleResponse(
            code=200, 
            description="Successful Response", 
            content_type="application/json", 
            examples=[
                Example(name="Logged out", summary="Logged out", description="Succesfully removed tokens from response", value=DefaultResponseModel(message="Logged out")), 
            ]
        )
    )
)
async def logout(
    response: Response,
    request: Request,
    db: Annotated[Session, Depends(DBSessionProvider)]
) -> DefaultResponseModel:
    
    if (access_token := request.cookies.get("access_token")):
        if not get_blacklist_token(db, BlacklistTokenElement(token=access_token)):
            decoded_at = jwt.decode(access_token, SECRET_KEY, algorithms=[ENCRYPTION_ALGORITHM])
            create_blacklist_token(db, BlacklistTokenElementFull(token=access_token, expiration_date=datetime.datetime.fromisoformat(decoded_at.get('expiration_date'))))
    
    if (refresh_token := request.cookies.get("refresh_token")):
        if not get_blacklist_token(db, BlacklistTokenElement(token=refresh_token)):
            decoded_rt = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ENCRYPTION_ALGORITHM])
            create_blacklist_token(db, BlacklistTokenElementFull(token=refresh_token, expiration_date=datetime.datetime.fromisoformat(decoded_rt.get('expiration_date'))))

    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")

    return DefaultResponseModel(message="Logged out")
    

@router.patch(
    "/token", 
    status_code=status.HTTP_201_CREATED,
    responses=Responses(
        CreateExampleResponse(
            code=201, 
            description="Successful Response", 
            content_type="application/json", 
            examples=[
                Example(name="Refreshed", summary="Refreshed", value=DefaultResponseModel(message="Refreshed")), 
            ]
        ),
        CreateRefreshResponses()
    )
)
async def refresh_for_access_token(
    response: Response,
    refresh_token: Annotated[RefreshToken, Depends(retrieve_refresh_token)]
) -> DefaultResponseModel:
    
    response.set_cookie(
        key="access_token", 
        value=f"""{create_token(
            {
                "user_id": refresh_token.user_id,
                "token_type": "Bearer",
                "type": "access",
                "expiration_date": (datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_TIME)).isoformat()
            }
        )}""",
        max_age=ACCESS_TOKEN_EXPIRE_TIME*60, 
        httponly=True
    )

    return DefaultResponseModel(message="Refreshed")