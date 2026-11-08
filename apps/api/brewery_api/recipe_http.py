"""Version 1 overview transport; domain services preserve the complete plan."""
from dataclasses import asdict
from decimal import Decimal
from ipaddress import ip_address, ip_network
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Path, Query, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, UUID4

from brewery_config import browser_trusted_hosts
from brewery_database.recipes import PostgresRecipeDraftStore
from brewery_domain.recipe_plan import Ingredient
from brewery_domain.recipes import DraftConflict, DraftNotFound, InvalidDraft, RecipeDraftService, RecipeStorageUnavailable


PREFIX = '/api/v1/recipe-drafts'
MAX_BODY_BYTES = 32768


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CreateDraftV1(StrictModel):
    creation_id: UUID4


class UpdateOverviewV1(StrictModel):
    expected_revision: Annotated[StrictInt, Field(ge=1, le=9007199254740991)]
    name: Annotated[StrictStr, Field(max_length=200)] | None
    description: Annotated[StrictStr, Field(max_length=10000)] | None


class RecipeOverviewV1(StrictModel):
    recipe_id: Annotated[str, Field(min_length=1, max_length=128)]
    version_id: Annotated[str, Field(min_length=1, max_length=128)]
    version_number: Annotated[int, Field(ge=1, le=2147483647)]
    name: str | None
    description: str | None
    edit_revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    status: Literal['draft']


class DraftPageV1(StrictModel):
    items: Annotated[list[RecipeOverviewV1], Field(max_length=100)]
    next_offset: Annotated[int, Field(ge=1, le=100000)] | None


class IngredientV1(StrictModel):
    id: Annotated[StrictStr, Field(min_length=1, max_length=128)]
    name: Annotated[StrictStr, Field(max_length=200)] | None
    category: Literal['grain', 'hops', 'yeast', 'other'] | None
    quantity: Annotated[StrictStr, Field(pattern=r'^(0|[1-9][0-9]{0,11})(\.[0-9]{1,12})?$')] | None
    unit: Literal['g', 'kg', 'oz', 'lb', 'mL', 'L', 'US_fl_oz', 'US_gal', 'count', 'packet'] | None


class UpdateIngredientsV1(StrictModel):
    expected_revision: Annotated[StrictInt, Field(ge=1, le=9007199254740991)]
    ingredients: Annotated[list[IngredientV1], Field(max_length=100)]


class StoredIngredientV1(StrictModel):
    # Reads preserve pre-existing storage values without imposing new write limits.
    id: str
    name: str | None
    category: str | None
    quantity: str | None
    unit: str | None


class IngredientsV1(StrictModel):
    version_id: str
    edit_revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    ingredients: list[StoredIngredientV1]


class FieldIssueV1(StrictModel):
    path: str
    code: str
    message: str


class ErrorDetailV1(StrictModel):
    code: Literal['validation_error', 'conflict', 'not_found', 'unavailable', 'forbidden',
                  'unsupported_media_type', 'request_too_large', 'invalid_request']
    message: str
    issues: list[FieldIssueV1] = Field(default_factory=list)


class RecipeErrorV1(StrictModel):
    error: ErrorDetailV1


def error_response(status, code, message, issues=()):
    return JSONResponse(status_code=status, content={'error': {'code': code, 'message': message,
                        'issues': list(issues)}}, headers={'Cache-Control': 'no-store'})


class RecipeRequestBoundary:
    """Local host/origin checks and bounded JSON input, before endpoint parsing."""
    def __init__(self, app, trusted_hosts):
        self.app, self.trusted_hosts = app, trusted_hosts

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if scope['type'] != 'http' or not (path == PREFIX or path.startswith(PREFIX + '/')):
            return await self.app(scope, receive, send)
        headers = {key.decode().lower(): value.decode('latin-1') for key, value in scope['headers']}

        async def cached_send(message):
            if message['type'] == 'http.response.start':
                message = {**message, 'headers': [(key, value) for key, value in message.get('headers', [])
                                                  if key.lower() != b'cache-control'] + [(b'cache-control', b'no-store')]}
            await send(message)

        async def reject(status, code, message):
            await error_response(status, code, message)(scope, receive, cached_send)

        try:
            host = urlsplit('//' + headers.get('host', ''))
            hostname, port = host.hostname, host.port
            if not hostname or host.username is not None or host.path or host.query or host.fragment:
                raise ValueError
            try:
                address = ip_address(hostname)
                allowed = address.is_private or address.is_loopback or address in ip_network('100.64.0.0/10')
            except ValueError:
                allowed = hostname.lower() in self.trusted_hosts
            if not allowed:
                raise ValueError
            if (origin := headers.get('origin')) is not None:
                parsed = urlsplit(origin)
                default = 443 if scope['scheme'] == 'https' else 80
                if (parsed.scheme != scope['scheme'] or parsed.hostname != hostname or parsed.username is not None
                        or parsed.path or parsed.query or parsed.fragment or (parsed.port or default) != (port or default)):
                    raise ValueError
            if headers.get('sec-fetch-site') == 'cross-site':
                raise ValueError
        except ValueError:
            return await reject(403, 'forbidden', 'Open the companion using its local hostname or address.')

        if scope['method'] in ('POST', 'PATCH'):
            if headers.get('content-type', '').split(';')[0].lower() != 'application/json':
                return await reject(415, 'unsupported_media_type', 'Recipe changes require JSON.')
            try:
                length = int(headers.get('content-length', '0'))
                if length < 0:
                    raise ValueError
            except ValueError:
                return await reject(400, 'invalid_request', 'Invalid request length.')
            if length > MAX_BODY_BYTES:
                return await reject(413, 'request_too_large', 'Recipe request exceeds the supported size.')
            body = bytearray()
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                data = message.get('body', b'')
                if len(body) + len(data) > MAX_BODY_BYTES:
                    return await reject(413, 'request_too_large', 'Recipe request exceeds the supported size.')
                body.extend(data)
                if not message.get('more_body', False):
                    break
            try:
                body.decode('utf-8')
            except UnicodeDecodeError:
                return await reject(400, 'invalid_request', 'Recipe JSON must use UTF-8 encoding.')
            original_receive = receive
            delivered = False

            async def buffered_receive():
                nonlocal delivered
                if delivered:
                    return await original_receive()
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}

            receive = buffered_receive
        await self.app(scope, receive, cached_send)


def install_recipe_routes(application):
    application.add_middleware(RecipeRequestBoundary, trusted_hosts=browser_trusted_hosts())
    router = APIRouter(prefix=PREFIX, tags=['Recipe drafts'], responses={
        status: {'model': RecipeErrorV1} for status in (400, 403, 404, 409, 413, 415, 422, 503)
    })

    def service(request):
        return RecipeDraftService(PostgresRecipeDraftStore(request.app.state.database))

    def result(value):
        return RecipeOverviewV1(**asdict(value), status='draft')

    def ingredient_result(stored):
        return IngredientsV1(version_id=stored.draft.plan.version_id, edit_revision=stored.edit_revision,
            ingredients=[StoredIngredientV1(id=item.id, name=item.name, category=item.category,
                quantity=format(item.quantity, 'f') if item.quantity is not None else None, unit=item.unit)
                for item in stored.draft.plan.ingredients])

    @router.get('', response_model=DraftPageV1)
    def list_drafts(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50,
                    offset: Annotated[int, Query(ge=0, le=100000)] = 0):
        items = service(request).store.list_drafts(limit + 1, offset)
        return DraftPageV1(items=[result(item) for item in items[:limit]],
                           next_offset=offset + limit if len(items) > limit and offset + limit <= 100000 else None)

    @router.post('', response_model=RecipeOverviewV1, status_code=201,
                 responses={200: {'model': RecipeOverviewV1, 'description': 'Creation key already exists'}})
    def create_draft(payload: CreateDraftV1, request: Request, response: Response):
        value, created = service(request).create_empty(payload.creation_id)
        response.status_code = 201 if created else 200
        return result(value)

    @router.get('/{version_id}', response_model=RecipeOverviewV1)
    def load_draft(version_id: Annotated[str, Path(min_length=1, max_length=128)], request: Request):
        return result(service(request).load(version_id))

    @router.patch('/{version_id}/overview', response_model=RecipeOverviewV1)
    def update_overview(version_id: Annotated[str, Path(min_length=1, max_length=128)], payload: UpdateOverviewV1, request: Request):
        return result(service(request).update_overview(version_id, payload.expected_revision,
                                                       payload.name, payload.description))

    @router.get('/{version_id}/ingredients', response_model=IngredientsV1)
    def load_ingredients(version_id: Annotated[str, Path(min_length=1, max_length=128)], request: Request):
        return ingredient_result(service(request).load_ingredients(version_id))

    @router.patch('/{version_id}/ingredients', response_model=IngredientsV1)
    def update_ingredients(version_id: Annotated[str, Path(min_length=1, max_length=128)], payload: UpdateIngredientsV1, request: Request):
        ingredients = tuple(Ingredient(item.id, version_id,
            Decimal(item.quantity) if item.quantity is not None else None, item.unit, item.name, item.category)
            for item in payload.ingredients)
        return ingredient_result(service(request).update_ingredients(version_id, payload.expected_revision, ingredients))

    @application.exception_handler(DraftNotFound)
    async def not_found(request, error):
        return error_response(404, 'not_found', 'This draft could not be found.')

    @application.exception_handler(DraftConflict)
    async def conflict(request, error):
        return error_response(409, 'conflict', 'This draft changed elsewhere. Review the latest saved version before retrying.')

    @application.exception_handler(InvalidDraft)
    async def invalid_draft(request, error):
        return error_response(422, 'validation_error', 'Check the highlighted fields.', [asdict(issue) for issue in error.issues])

    @application.exception_handler(RecipeStorageUnavailable)
    async def unavailable(request, error):
        return error_response(503, 'unavailable', 'Recipe storage is unavailable. Your entered values have not been saved.')

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        if not request.url.path.startswith(PREFIX):
            return await request_validation_exception_handler(request, error)
        issues = [{'path': '.'.join(str(part) for part in issue['loc'] if part != 'body'),
                   'code': issue['type'], 'message': issue['msg']} for issue in error.errors()]
        return error_response(422, 'validation_error', 'Check the highlighted fields.', issues)

    application.include_router(router)
