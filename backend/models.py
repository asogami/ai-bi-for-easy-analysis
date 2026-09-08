from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Dimension(StrictModel):
    field: str
    grain: Literal['value', 'year', 'month', 'day'] = 'value'


class Measure(StrictModel):
    field: str
    aggregate: Literal['sum', 'avg', 'min', 'max', 'count', 'count_distinct']
    label: str = Field(min_length=1, max_length=120)


class Filter(StrictModel):
    field: str
    operator: Literal['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'contains', 'in', 'is_null', 'not_null']
    value: str | int | float | bool | list[str | int | float] | None = None


class ChartPlan(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    dataset: str
    chart_type: Literal['bar', 'line', 'table', 'kpi']
    dimensions: list[Dimension] = Field(default_factory=list, max_length=2)
    measures: list[Measure] = Field(min_length=1, max_length=4)
    filters: list[Filter] = Field(default_factory=list, max_length=12)
    sort_by: str = 'm0'
    sort_direction: Literal['asc', 'desc'] = 'desc'
    limit: int = Field(default=30, ge=1, le=200)


class ReportPlan(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    explanation: str = Field(default='', max_length=2000)
    clarification: str | None = Field(default=None, max_length=1500)
    charts: list[ChartPlan] = Field(default_factory=list, max_length=4)


class AskRequest(StrictModel):
    question: str = Field(min_length=3, max_length=4000)
    previous_plan: ReportPlan | None = None


class FieldDescription(StrictModel):
    name: str
    description: str = Field(max_length=1000)


class DatasetDescription(StrictModel):
    name: str
    description: str = Field(max_length=2000)
    fields: list[FieldDescription] = Field(max_length=400)


class ContextUpdate(StrictModel):
    company_description: str = Field(max_length=2000)
    business_rules: list[str] = Field(max_length=30)
    datasets: list[DatasetDescription] = Field(max_length=9)
