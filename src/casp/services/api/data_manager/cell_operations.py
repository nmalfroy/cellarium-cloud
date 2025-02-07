import typing as t
import uuid
from datetime import datetime, timedelta

from google.cloud import bigquery

from casp.data_manager import BaseDataManager, sql
from casp.services import settings
from casp.services.api.clients.matching_client import MatchResult
from casp.services.api.data_manager import bigquery_response_parsers, bigquery_schemas, cellarium_general
from casp.services.db import models


class CellOperationsDataManager(BaseDataManager):
    """
    Data Manager for making data operations in Cellarium Cloud storage.
    """

    # Directories for SQL templates
    CELL_ANALYSIS_TEMPLATE_DIR = f"{settings.SERVICES_DIR}/api/data_manager/sql_templates/cell_operations"

    # SQL template file paths
    SQL_MATCH_METADATA = f"{CELL_ANALYSIS_TEMPLATE_DIR}/get_neighborhood_distance_summary.sql.mako"
    SQL_MATCH_METADATA_DEV_DETAILS = (
        f"{CELL_ANALYSIS_TEMPLATE_DIR}/get_neighborhood_distance_summary_dev_details.sql.mako"
    )
    SQL_GET_CELLS_BY_IDS = f"{CELL_ANALYSIS_TEMPLATE_DIR}/get_cell_metadata_by_ids.sql.mako"

    def insert_matches_to_temp_table(self, query_ids: t.List[str], knn_response: MatchResult) -> str:
        """
        Insert matches to temporary table in async manner in a separate thread.

        Note: This function executes I/O-bound operation (BigQuery insert) in a separate thread to avoid blocking the
        main thread. Parsing of the response is done in the main thread in sync manner.

        :param query_ids: List of query ids (original cell ids from the input file).
        :param knn_response: MatchResult returned by space vector search service.

        :return: The fully-qualified name of the temporary table.
        """
        my_uuid = str(uuid.uuid4())[:8]
        temp_table_fqn = f"{settings.API_REQUEST_TEMP_TABLE_DATASET}.api_request_matches_{my_uuid}"
        table = bigquery.Table(temp_table_fqn, schema=bigquery_schemas.MATCH_CELL_RESULTS_SCHEMA)
        table.expires = datetime.now().astimezone() + timedelta(
            minutes=settings.API_REQUEST_TEMP_TABLE_DATASET_EXPIRATION
        )

        self.block_coo_matrix_db_client.create_table(table)

        rows_to_insert = []
        for i in range(0, len(knn_response.matches)):
            query_id = query_ids[i]
            for neighbor in knn_response.matches[i].neighbors:
                rows_to_insert.append(
                    {
                        "query_id": str(query_id),
                        "match_cas_cell_index": int(neighbor.cas_cell_index),
                        "match_score": float(neighbor.distance),
                    }
                )

        job_config = bigquery.LoadJobConfig(schema=bigquery_schemas.MATCH_CELL_RESULTS_SCHEMA)

        job = self.block_coo_matrix_db_client.load_table_from_json(
            json_rows=rows_to_insert, destination=temp_table_fqn, job_config=job_config
        )

        job.result()  # Wait for the job to complete

        return temp_table_fqn

    def get_neighborhood_distance_summary(
        self, cas_model: models.CASModel, match_temp_table_fqn: str
    ) -> t.List[t.Dict[str, t.Any]]:
        """
        Execute a BigQuery query to retrieve metadata for a matching query.

        :param cas_model: The CASModel containing dataset information
        :param match_temp_table_fqn: The fully-qualified name of the temporary table.

        :return: The BigQuery job object representing the query execution.
        """
        sql_template_data = sql.TemplateData(
            project=self.project, dataset=cas_model.bq_dataset_name, temp_table_fqn=match_temp_table_fqn
        )
        sql_query = sql.render(self.SQL_MATCH_METADATA, template_data=sql_template_data)

        query_job = self.block_coo_matrix_db_client.query(query=sql_query)

        return bigquery_response_parsers.parse_match_query_job(query_job=query_job)

    def get_neighborhood_distance_summary_dev_details(
        self, cas_model: models.CASModel, match_temp_table_fqn: str
    ) -> t.List[t.Dict[str, t.Any]]:
        """
        Execute a BigQuery query to retrieve metadata for a matching query. The returned query, similar to
        :meth:`get_match_query_metadata`, includes a breakdown of the number of cells that matched each cell type
        by dataset.

        :param cas_model: The CASModel containing dataset information
        :param match_temp_table_fqn: The fully-qualified name of the temporary table.

        :return: The BigQuery job object representing the query execution.
        """
        sql_template_data = sql.TemplateData(
            project=self.project, dataset=cas_model.bq_dataset_name, temp_table_fqn=match_temp_table_fqn
        )
        sql_query = sql.render(self.SQL_MATCH_METADATA_DEV_DETAILS, template_data=sql_template_data)

        query_job = self.block_coo_matrix_db_client.query(query=sql_query)

        return bigquery_response_parsers.parse_match_query_job(query_job=query_job, include_dev_details=True)

    def get_cell_metadata_by_ids(
        self, cell_ids: t.List[int], metadata_feature_names: t.List[str], model_name: str
    ) -> t.List[t.Dict[str, t.Any]]:
        """
        Get cells by ids.

        :param cell_ids: Cas cell indexes from Big Query
        :param metadata_feature_names: Metadata features to return from Big Query `cas_cell_info` table
        :param model_name: Name of the model to query. Used to get the dataset name where to get the cells from

        :return: List of dictionaries representing the query results.
        """
        cellarium_general_data_manager = cellarium_general.CellariumGeneralDataManager()
        model = cellarium_general_data_manager.get_model_by_name(model_name=model_name)

        template_data = sql.TemplateData(
            project=self.project,
            dataset=model.bq_dataset_name,
            select=metadata_feature_names,
            filters={"cas_cell_index__in": cell_ids},
        )
        sql_query = sql.render(template_path=self.SQL_GET_CELLS_BY_IDS, template_data=template_data)

        query_job = self.block_coo_matrix_db_client.query(query=sql_query)

        return bigquery_response_parsers.parse_get_cells_job(
            query_job=query_job, cell_metadata_features=metadata_feature_names
        )
