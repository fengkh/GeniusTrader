from uuid import UUID

from fastapi import APIRouter, Request, status

from app.api.dependencies import CurrentUser, SessionDependency, SettingsDependency, get_request_id
from app.schemas.ai import AIProviderCreate, AIProviderOut, AIProviderTestResult, AIProviderUpdate
from app.schemas.common import DataEnvelope, MessageResponse
from app.services.ai_providers import (
    create_ai_provider,
    delete_ai_provider,
    get_provider_or_404,
    list_ai_providers,
    provider_to_out,
    test_ai_provider,
    update_ai_provider,
)

router = APIRouter()


@router.get("", response_model=DataEnvelope[list[AIProviderOut]])
async def list_providers(
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, list[AIProviderOut]]:
    providers = await list_ai_providers(session, current_user.id)
    return {"data": [provider_to_out(provider) for provider in providers]}


@router.post("", response_model=DataEnvelope[AIProviderOut], status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: AIProviderCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, AIProviderOut]:
    provider = await create_ai_provider(
        session,
        user_id=current_user.id,
        payload=payload,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": provider_to_out(provider)}


@router.get("/{provider_id}", response_model=DataEnvelope[AIProviderOut])
async def get_provider(
    provider_id: UUID,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, AIProviderOut]:
    provider = await get_provider_or_404(session, user_id=current_user.id, provider_id=provider_id)
    return {"data": provider_to_out(provider)}


@router.patch("/{provider_id}", response_model=DataEnvelope[AIProviderOut])
async def patch_provider(
    provider_id: UUID,
    payload: AIProviderUpdate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, AIProviderOut]:
    provider = await update_ai_provider(
        session,
        user_id=current_user.id,
        provider_id=provider_id,
        payload=payload,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": provider_to_out(provider)}


@router.delete("/{provider_id}", response_model=DataEnvelope[MessageResponse])
async def delete_provider(
    provider_id: UUID,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> dict[str, MessageResponse]:
    await delete_ai_provider(
        session,
        user_id=current_user.id,
        provider_id=provider_id,
        request_id=get_request_id(request),
    )
    return {"data": MessageResponse()}


@router.post("/{provider_id}/test", response_model=DataEnvelope[AIProviderTestResult])
async def test_provider(
    provider_id: UUID,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
    settings: SettingsDependency,
) -> dict[str, AIProviderTestResult]:
    result = await test_ai_provider(
        session,
        user_id=current_user.id,
        provider_id=provider_id,
        settings=settings,
        request_id=get_request_id(request),
    )
    return {"data": result}
