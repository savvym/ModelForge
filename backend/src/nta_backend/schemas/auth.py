from uuid import UUID

from pydantic import BaseModel


class CurrentUserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    status: str
    current_project_id: UUID
    current_project_code: str
    current_project_name: str
    current_project_role: str
