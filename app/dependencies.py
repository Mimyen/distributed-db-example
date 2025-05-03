from typing import Annotated, Literal, Optional, Union
from typing_extensions import Doc
from fastapi import Request, Header, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, OAuth2
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi.security.utils import get_authorization_scheme_param
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.config import ACCESS_TOKEN_EXPIRE_TIME, SECRET_KEY, ENCRYPTION_ALGORITHM, REFRESH_TOKEN_EXPIRE_TIME, CHECK_IF_ACTIVE
from uuid import uuid4
from pydantic import BaseModel
from app.domain.user.service import get_user_by_email_and_password, get_user
from app.domain.token_blacklist.service import create_blacklist_token, get_blacklist_token
from app.domain.token_blacklist.schemas import BlacklistTokenElement
from jinja2 import Template
from functools import wraps
import jwt
import datetime
import os
import re

class DefaultResponseModel(BaseModel):
    """Used for type hinting and creating examples"""
    message: str

class DefaultErrorModel(BaseModel):
    """Used for creating examples"""
    detail: str

class Example(BaseModel):
    """
    Used for making example response in CreateExampleResponse function
    """
    name: str
    summary: str | None = None
    description: str | None = None
    value: dict | list | BaseModel | str | int | float

def CreateExampleResponse(
    *,
    code: int,
    description: str = '',
    content_type: Literal[
        'text/plain', 
        'text/html', 
        'text/css', 
        'text/javascript', 
        'text/csv', 
        'text/xml', 
        'text/markdown', 
        'application/json', 
        'application/xml', 
        'application/octet-stream',
        'application/pdf',
        'application/zip',
        'application/x-www-form-urlencoded',
        'application/vnd.api+json',
        'application/ld+json',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'image/png',
        'image/jpeg',
        'image/gif',
        'image/svg+xml',
        'image/webp',
        'image/bmp',
        'image/tiff',
        'image/x-icon',
        'audio/mpeg',
        'audio/ogg',
        'audio/wav',
        'audio/aac',
        'video/mp4',
        'video/webm',
        'video/ogg',
        'video/x-msvideo',
        'multipart/form-data',
        'multipart/mixed',
        'multipart/alternative',
        'application/javascript',
        'application/x-tar',
        'application/x-rar-compressed',
        'application/x-bzip',
        'application/x-bzip2',
        'application/x-shockwave-flash',
        'application/vnd.android.package-archive',
        '*/*'
    ] = 'application/json',
    examples: list[Example] = [Example(name="Example", summary=None, description=None, value=DefaultResponseModel(message="example"))]
) -> dict[int, dict[str, any]]:
    """
    Allows for quick docs building

    Pydantic models can be used as value for example

    Raises `AttributeError` when amount of examples is `<0`

    Usage:
    ```python
    @router.get(
        "/get", 
        status_code=status.HTTP_200_OK,
        responses={
            **CreateExampleResponse(
                code=200, 
                description="Pawel", 
                content_type="application/json", 
                examples=[
                    Example(name="Pawel", summary="Pawel", description="Pawel kox", value={"message": "pawel"}), 
                    Example(name="Kox", summary="Kox", description="Pawel kox", value={"message": "pawel kox"})
                ]
            ),
        }
    )
    ```
    """

    if len(examples) < 1: 
        raise AttributeError(name="You need to provide atleast one example")

    return { 
        code: {
            "description": description,
            "content": {
                content_type: {
                    "examples": {
                        example.name: {
                            "summary": example.summary,
                            "description": example.description,
                            "value": example.value
                        }
                        for example in examples
                    }
                }
            }
        }
    }

def Responses(
    *ExampleResponses: dict[int, dict[str, any]]
) -> dict[int, dict[str, any]]:
    """
    Merges the example responses for fastapi endpoint 

    **Usage**:
    ```python
    @router.post(
        "/",
        status_code=200, 
        responses=Responses(
            CreateExampleResponse(...),
            ...
        )
    )
    ```
    **Isn't neccessary, instead you can unpack CreateExampleResponse in dictionary, but it may not always work as intended**:
    ```python
    @router.post(
        "/",
        status_code=200, 
        responses={
            **CreateExampleResponse(...),
            ...
        }
    )
    ```
    """
    
    output = {}

    for example in ExampleResponses:
        if [*example][0] not in [*output]: output.update({**example})
        else:
            for content in [*example[[*example][0]]['content']]:
                if content in [*output[[*example][0]]['content']]:
                    output[[*example][0]]['content'][content]['examples'].update({**example[[*example][0]]['content'][content]['examples']})
                else:
                    output[[*example][0]]['content'].update({**output[[*example][0]]['content'][content]})

    return output

conf = ConnectionConfig(
    MAIL_USERNAME=os.environ.get("EMAIL"),
    MAIL_PASSWORD=os.environ.get("PASSWORD"),
    MAIL_FROM=os.environ.get("EMAIL"),
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_FROM_NAME="ReadIt",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER='app/templates/email'
)


class MyOAuth2PasswordRequestForm:
    """
    This is a dependency class to collect the `username` and `password` as form data
    for an OAuth2 password flow.

    The OAuth2 specification dictates that for a password flow the data should be
    collected using form data (instead of JSON) and that it should have the specific
    fields `username` and `password`.

    All the initialization parameters are extracted from the request.

    Read more about it in the
    [FastAPI docs for Simple OAuth2 with Password and Bearer](https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/).

    ## Example

    ```python
    from typing import Annotated

    from fastapi import Depends, FastAPI
    from fastapi.security import OAuth2PasswordRequestForm

    app = FastAPI()


    @app.post("/login")
    def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
        data = {}
        data["scopes"] = []
        for scope in form_data.scopes:
            data["scopes"].append(scope)
        if form_data.client_id:
            data["client_id"] = form_data.client_id
        if form_data.client_secret:
            data["client_secret"] = form_data.client_secret
        return data
    ```

    Note that for OAuth2 the scope `items:read` is a single scope in an opaque string.
    You could have custom internal logic to separate it by colon caracters (`:`) or
    similar, and get the two parts `items` and `read`. Many applications do that to
    group and organize permissions, you could do it as well in your application, just
    know that that it is application specific, it's not part of the specification.
    """

    def __init__(
        self,
        *,
        grant_type: Annotated[
            Union[str, None],
            Form(pattern="password"),
            Doc(
                """
                The OAuth2 spec says it is required and MUST be the fixed string
                "password". Nevertheless, this dependency class is permissive and
                allows not passing it. If you want to enforce it, use instead the
                `OAuth2PasswordRequestFormStrict` dependency.
                """
            ),
        ] = None,
        email: Annotated[
            str,
            Form(),
            Doc(
                """
                `email` string. The OAuth2 spec requires the exact field name
                `email`.
                """
            ),
        ],
        password: Annotated[
            str,
            Form(),
            Doc(
                """
                `password` string. The OAuth2 spec requires the exact field name
                `password".
                """
            ),
        ],
        scope: Annotated[
            str,
            Form(),
            Doc(
                """
                A single string with actually several scopes separated by spaces. Each
                scope is also a string.

                For example, a single string with:

                ```python
                "items:read items:write users:read profile openid"
                ````

                would represent the scopes:

                * `items:read`
                * `items:write`
                * `users:read`
                * `profile`
                * `openid`
                """
            ),
        ] = "",
        client_id: Annotated[
            Union[str, None],
            Form(),
            Doc(
                """
                If there's a `client_id`, it can be sent as part of the form fields.
                But the OAuth2 specification recommends sending the `client_id` and
                `client_secret` (if any) using HTTP Basic auth.
                """
            ),
        ] = None,
        client_secret: Annotated[
            Union[str, None],
            Form(),
            Doc(
                """
                If there's a `client_password` (and a `client_id`), they can be sent
                as part of the form fields. But the OAuth2 specification recommends
                sending the `client_id` and `client_secret` (if any) using HTTP Basic
                auth.
                """
            ),
        ] = None,
    ):
        self.grant_type = grant_type
        self.password = password
        self.email = email
        self.scopes = scope.split()
        self.client_id = client_id
        self.client_secret = client_secret

def DBSessionProvider():
    """
    Function responsible for giving access to database

    *Usage*:

    ```python
    async def register_user(
        ...,
        db: Annotated[Session, Depends(DBSessionProvider)]
    ) -> DefaultResponseModel:
        ...
        db.commit()
        ...
    ```
    """
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class EncodedTokens(BaseModel):
    access_token: str | None
    refresh_token: str | None

class AccessToken(BaseModel):
    user_id: int
    expiration_date: str
    token_type: str
    type: str

class RefreshToken(BaseModel):
    user_id: int
    expiration_date: str
    token_type: str
    type: str

class Tokens(BaseModel):
    access_token: AccessToken | None
    refresh_token: RefreshToken | None

class OAuth2PasswordBearerWithCookie(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: Optional[str] = None,
        scopes: Optional[dict[str, str]] = None,
        auto_error: bool = True,
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlowsModel(password={"tokenUrl": tokenUrl, "scopes": scopes})
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[str]:
        authorization: str | None = request.cookies.get("access_token")  #changed to accept access token from httpOnly Cookie
        reauthorization: str | None = request.cookies.get("refresh_token")

        return EncodedTokens(access_token=authorization, refresh_token=reauthorization)

oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="oauth2/token", scheme_name="MyOAuth2PasswordRequestForm")

def retrieve_tokens(
    token: Annotated[Tokens, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(DBSessionProvider)]
) -> Tokens:
    
    if not token.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credentials'
        )
    
    if not token.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credentials'
        )
    
    if get_blacklist_token(db, BlacklistTokenElement(token=token.access_token)) or get_blacklist_token(db, BlacklistTokenElement(token=token.access_token)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Blacklisted token'
        )

    decoded_access_token = jwt.decode(token.access_token, SECRET_KEY, algorithms=[ENCRYPTION_ALGORITHM])
    decoded_refresh_token = jwt.decode(token.refresh_token, SECRET_KEY, algorithms=[ENCRYPTION_ALGORITHM])

    access_token = AccessToken(
        user_id=decoded_access_token.get("user_id"),
        type=decoded_access_token.get("type"),
        token_type=decoded_access_token.get("token_type"),
        expiration_date=decoded_access_token.get("expiration_date")
    )
    refresh_token = RefreshToken(
        user_id=decoded_refresh_token.get("user_id"),
        type=decoded_refresh_token.get("type"),
        token_type=decoded_refresh_token.get("token_type"),
        expiration_date=decoded_refresh_token.get("expiration_date")
    )

    if datetime.datetime.now(datetime.UTC) > datetime.datetime.fromisoformat(refresh_token.expiration_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Outdated refresh_token'
        )
    
    if datetime.datetime.now(datetime.UTC) > datetime.datetime.fromisoformat(access_token.expiration_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Outdated access_token'
        )

    return Tokens(access_token=access_token, refresh_token=refresh_token)



def retrieve_access_token(
    token: Annotated[Tokens, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(DBSessionProvider)]
) -> AccessToken:

    if not token.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credentials'
        )

    decoded_access_token = jwt.decode(token.access_token, SECRET_KEY, algorithms=[ENCRYPTION_ALGORITHM])

    access_token = AccessToken(
        user_id=decoded_access_token.get("user_id"),
        type=decoded_access_token.get("type"),
        token_type=decoded_access_token.get("token_type"),
        expiration_date=decoded_access_token.get("expiration_date")
    )

    if datetime.datetime.now(datetime.UTC) > datetime.datetime.fromisoformat(access_token.expiration_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Outdated access_token'
        )

    return access_token



def retrieve_refresh_token(
    token: Annotated[Tokens, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(DBSessionProvider)]
) -> RefreshToken:
    
    if not token.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credentials'
        )
    
    decoded_refresh_token = jwt.decode(token.refresh_token, SECRET_KEY, algorithms=[ENCRYPTION_ALGORITHM])

    refresh_token = RefreshToken(
        user_id=decoded_refresh_token.get("user_id"),
        type=decoded_refresh_token.get("type"),
        token_type=decoded_refresh_token.get("token_type"),
        expiration_date=decoded_refresh_token.get("expiration_date")
    )

    if datetime.datetime.now(datetime.UTC) > datetime.datetime.fromisoformat(refresh_token.expiration_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Outdated refresh_token'
        )

    return refresh_token



def create_token(
    item: dict[str, any],
    token_type: str = "Bearer"
) -> str:
    item.update({"token_type": token_type})
    return jwt.encode(item, SECRET_KEY, algorithm=ENCRYPTION_ALGORITHM)


def ValidateCredentials(
    form_data: Annotated[MyOAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(DBSessionProvider)]
) -> EncodedTokens:

    # Analyze credentials
    if not (user := get_user_by_email_and_password(db, form_data.email, form_data.password)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credentials'
        )
    
    if CHECK_IF_ACTIVE:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Activate your account'
            )

    # Attempt creating the token
    try:
        access_token = create_token({
            "user_id": user.id,
            "expiration_date": (datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_TIME)).isoformat(),
            "type": "access"
        })
        refresh_token = create_token({
            "user_id": user.id,
            "expiration_date": (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_TIME)).isoformat(),
            "type": "refresh"
        })
    except jwt.PyJWTError:
        raise HTTPException
    
    # return {"access_token": access_token, "refresh_token": refresh_token}
    return EncodedTokens(access_token=access_token, refresh_token=refresh_token)


def CreateAuthResponses():
    return CreateExampleResponse(
        code=400,
        description='Bad Request',
        content_type='application/json',
        examples=[
            Example(name="Invalid credentials", summary="Invalid credentials", description="Provided credentials are incorrect", value=DefaultErrorModel(detail="Invalid credentials")),
            Example(name="Inactive account", summary="Inactive account", description="Account isn't activated", value=DefaultErrorModel(detail="Activate your account")),
        ]
    )

def CreateAuthorizeResponses():
    return CreateExampleResponse(
        code=400,
        description='Bad Request',
        content_type='application/json',
        examples=[
            Example(name="Invalid credentials", summary="Invalid credentials", description="Provided credentials are incorrect", value=DefaultErrorModel(detail="Invalid credentials")),
            Example(name="Inactive account", summary="Inactive account", description="Account isn't activated", value=DefaultErrorModel(detail="Activate your account")),
            Example(name="Blacklisted token", summary="Blacklisted token", description="Token has been blacklisted due to being removed", value=DefaultErrorModel(detail="Blacklisted token")),
            Example(name="Outdated access token", summary="Outdated access token", description="Access token expiration date has passed", value=DefaultErrorModel(detail="Outdated access_token")),
            Example(name="Outdated refresh token", summary="Outdated refresh token", description="Refresh token expiration date has passed", value=DefaultErrorModel(detail="Outdated refresh_token")),
        ]
    )

def CreateRefreshResponses():
    return CreateExampleResponse(
        code=400,
        description='Bad Request',
        content_type='application/json',
        examples=[
            Example(name="Invalid credentials", summary="Invalid credentials", description="Provided credentials are incorrect", value=DefaultErrorModel(detail="Invalid credentials")),
            Example(name="Inactive account", summary="Inactive account", description="Account isn't activated", value=DefaultErrorModel(detail="Activate your account")),
            Example(name="Blacklisted token", summary="Blacklisted token", description="Token has been blacklisted due to being removed", value=DefaultErrorModel(detail="Blacklisted token")),
            Example(name="Outdated refresh token", summary="Outdated refresh token", description="Refresh token expiration date has passed", value=DefaultErrorModel(detail="Outdated refresh_token")),
        ]
    )

def Authorize(
    request: Request,
    access_token: Annotated[AccessToken, Depends(retrieve_access_token)],
    db: Annotated[Session, Depends(DBSessionProvider)]
) -> int:
    if request.cookies.get("access_token"):
        if get_blacklist_token(db, BlacklistTokenElement(token=request.cookies.get("access_token"))):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Blacklisted token'
            )
    
    if not (user := get_user(db, access_token.user_id)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credentials'
        )
    
    if CHECK_IF_ACTIVE:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Activate your account'
            )

    return access_token.user_id



def get_or_create(
    session, 
    model, 
    **kwargs
):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return instance
    


async def send_email(
    subject: str, 
    email_to: str, 
    body: dict[str, str], 
    template: str
) -> None:

    with open(f'app/templates/email/{template}') as file_:
        template = Template(file_.read())
        rendered_template = template.render(**body)
    
    message = MessageSchema(
        subject=subject,
        recipients=[email_to],
        body=rendered_template,
        subtype='html',
    )
    
    fm = FastMail(conf)
    await fm.send_message(message)



def validate_password(
    password: str
):
    
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password is too short (atleast 8 chars)")
    if not re.search(r'[A-Z]', password):
        raise HTTPException(status_code=400, detail="Password must have astleast 1 capital letter")
    if not re.search(r'[0-9]', password):
        raise HTTPException(status_code=400, detail="Password must have astleast 1 number")
    if not re.search(r'[\W_]', password):
        raise HTTPException(status_code=400, detail="Password must have astleast 1 special sign")
    

def CreateInternalErrorResponse():
    return CreateExampleResponse(
        code=500,
        description="Internal Server Error",
        content_type="application/json",
        examples=[
            Example(name="Internal Server Error", summary="Internal Server Error", description="Error inside server code, please notify backend developer about the error", value=DefaultErrorModel(detail="Internal Server Error"))
        ]
    )