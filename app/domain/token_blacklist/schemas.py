from pydantic import BaseModel
from datetime import datetime

class BlacklistTokenElement(BaseModel):
    token: str

class BlacklistTokenElementFull(BlacklistTokenElement):
    expiration_date: datetime