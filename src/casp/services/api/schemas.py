import typing as t

from pydantic import BaseModel, Field


class MatchInfo(BaseModel):
    cell_type: str = Field(example="erythrocyte")
    cell_count: int = Field(example=94)
    min_distance: float = Field(example=1589.847900390625)
    p25_distance: float = Field(example=1664.875244140625)
    median_distance: float = Field(example=1791.372802734375)
    p75_distance: float = Field(example=1801.3585205078125)
    max_distance: float = Field(example=1840.047119140625)


class DevDetailObject(BaseModel):
    dataset_id: str = Field(example="a7a92fb49-50741b00a-244955d47")
    count_per_dataset: int = Field(example=10)
    min_distance: float = Field(example=1589.847900390625)
    max_distance: float = Field(example=1840.047119140625)
    median_distance: float = Field(example=1791.372802734375)
    mean_distance: float = Field(example=1791.372802734375)


class MatchInfoDevDetails(MatchInfo):
    dataset_ids_with_counts: t.List[DevDetailObject]


class QueryCell(BaseModel):
    query_cell_id: str = Field(example="ATTACTTATTTAGTT-12311")
    matches: t.List[MatchInfo]


class QueryCellDevDetails(BaseModel):
    query_cell_id: str = Field(example="ATTACTTATTTAGTT-12311")
    matches: t.List[MatchInfoDevDetails]


class CASModel(BaseModel):
    model_name: str = Field(example="incremental-pca-001")
    schema_name: str = Field(example="refdata-gex-mm10-2020-A")
    is_default_model: bool = Field(example=False)
    embedding_dimension: int = Field(example=512)

    class Config:
        orm_mode = True


class FeatureSchemaInfo(BaseModel):
    schema_name: str = Field(example="refdata-gex-mm10-2020-A")


class ApplicationInfo(BaseModel):
    application_version: str
    default_feature_schema: str = Field(example="refdata-gex-GRCh38-2020-A")
