"""Versioned, bounded transport for the pure C1 conversion calculator."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Annotated, Literal

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from brewery_config import browser_trusted_hosts
from brewery_domain.extract_conversion import ConversionInputError, FermentableYield, Mass, convert_fermentable
from .recipe_http import RecipeRequestBoundary, error_response


PREFIX = '/api/v1/conversions'
MassUnitV1 = Literal['g', 'kg', 'oz', 'lb']
DecimalText = Annotated[StrictStr, Field(max_length=26, pattern=r'^(0|[1-9][0-9]{0,12})(\.[0-9]{1,12})?$')]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class MassV1(StrictModel):
    amount: DecimalText
    unit: MassUnitV1


class YieldV1(StrictModel):
    potential_ppg: DecimalText
    recovery_fraction: DecimalText
    comparison_point: Literal['kettle', 'fermenter']
    provenance: Annotated[StrictStr, Field(min_length=1, max_length=1000, pattern=r'^[^\x00]*[^\x00\s][^\x00]*$')]


class FermentableConversionRequestV1(StrictModel):
    source_mass: MassV1
    source_yield: YieldV1
    target_yield: YieldV1
    target_unit: MassUnitV1


class RationalV1(StrictModel):
    numerator: Annotated[str, Field(pattern=r'^[0-9]+$')]
    denominator: Annotated[str, Field(pattern=r'^[1-9][0-9]*$')]


class FermentableConversionResponseV1(StrictModel):
    source_mass: MassV1
    source_yield: YieldV1
    target_yield: YieldV1
    amount: RationalV1
    unit: MassUnitV1
    gravity_points_gallons: RationalV1
    display_amount: Annotated[str, Field(pattern=r'^([0-9]+\.[0-9]{6}|<0\.000001)$')]
    display_decimal_places: Literal[6]
    calculation_version: Literal['gravity-equivalence/v1']


class ConversionIssueV1(StrictModel):
    path: str
    code: str
    message: str


class ConversionErrorDetailV1(StrictModel):
    code: Literal['invalid_conversion', 'forbidden', 'unsupported_media_type', 'request_too_large', 'invalid_request']
    message: str
    issues: list[ConversionIssueV1] = Field(default_factory=list)


class ConversionErrorV1(StrictModel):
    error: ConversionErrorDetailV1


def install_conversion_routes(application):
    application.add_middleware(RecipeRequestBoundary, trusted_hosts=browser_trusted_hosts(), prefix=PREFIX)
    router = APIRouter(prefix=PREFIX, tags=['Conversion calculator'], responses={
        status: {'model': ConversionErrorV1} for status in (400, 403, 413, 415, 422)
    })

    @router.post('/fermentable', response_model=FermentableConversionResponseV1)
    def convert(payload: FermentableConversionRequestV1):
        def yield_value(value):
            return FermentableYield(Decimal(value.potential_ppg), Decimal(value.recovery_fraction),
                                    value.comparison_point, value.provenance)
        try:
            result = convert_fermentable(Mass(Decimal(payload.source_mass.amount), payload.source_mass.unit),
                                        yield_value(payload.source_yield), yield_value(payload.target_yield), payload.target_unit)
        except ConversionInputError as error:
            return error_response(422, 'invalid_conversion', 'Check the highlighted conversion fields.',
                                  [{'path': error.path, 'code': 'invalid_input', 'message': str(error)}])
        def rational(value):
            return RationalV1(numerator=str(value.numerator), denominator=str(value.denominator))
        # Display only: the exact fraction remains authoritative and can be chained.
        with localcontext() as context:
            context.prec = 200
            context.rounding = ROUND_HALF_UP
            display = (Decimal(result.amount.numerator) / Decimal(result.amount.denominator)).quantize(Decimal('.000001'))
        return FermentableConversionResponseV1(source_mass=payload.source_mass,
            source_yield=payload.source_yield, target_yield=payload.target_yield,
            amount=rational(result.amount), unit=result.unit,
            gravity_points_gallons=rational(result.gravity_points_gallons),
            display_amount='<0.000001' if display == 0 else format(display, 'f'),
            display_decimal_places=6, calculation_version=result.calculation_version)

    previous_validation_handler = application.exception_handlers[RequestValidationError]

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        if not (request.url.path == PREFIX or request.url.path.startswith(PREFIX + '/')):
            return await previous_validation_handler(request, error)
        issues = [{'path': '.'.join(str(part) for part in issue['loc'] if part != 'body'),
                   'code': issue['type'], 'message': issue['msg']} for issue in error.errors()]
        malformed = any(issue['type'] == 'json_invalid' for issue in error.errors())
        return error_response(400 if malformed else 422, 'invalid_request' if malformed else 'invalid_conversion',
                              'Supply valid JSON.' if malformed else 'Check the highlighted conversion fields.', issues)

    application.include_router(router)
