import sys
from typing import Type

import duckdb
import pandas as pd
from pydantic import BaseModel, ValidationError

from trails.sources.oregon_hikers import (
    get_oh_sample_hikes_df,
    get_oh_backpackable_hikes_df,
)


def ingest_sample_oh_hikes():
    df = get_oh_sample_hikes_df()

    conn = duckdb.connect()
    conn.register("oh_hikes_sample", df)
    conn.execute("CREATE TABLE oh_hikes AS SELECT * FROM oh_hikes")
    result = conn.execute("SELECT * FROM oh_hikes")

    result.fetch_df().to_csv("oh_hikes.csv", index=False)


def ingest_oh_backpackable_hikes():
    df = get_oh_backpackable_hikes_df()

    conn = duckdb.connect()
    # Ingest dataframe into database
    conn.register("oh_hikes", df)
    conn.execute("CREATE TABLE oh_hikes AS SELECT * FROM oh_hikes")
    # Select top 5 rows from database
    result = conn.execute("SELECT * FROM oh_hikes")
    result.fetch_df().to_parquet("raw_oh_hikes.parquet", index=False)


class DataFrameValidationError(Exception):
    """Custom exception for DataFrame validation errors."""


def validate_dataframe(df: pd.DataFrame, model: Type[BaseModel]):
    """
    Validates each row of a DataFrame against a Pydantic model.
    Raises DataFrameValidationError if any row fails validation.

    :param df: DataFrame to validate.
    :param model: Pydantic model to validate against.
    :raises: DataFrameValidationError
    """
    errors = []

    for i, row in enumerate(df.to_dict(orient="records")):
        try:
            model(**row)
        except ValidationError as e:
            errors.append(f"Row {i} failed validation: {e}")

    if errors:
        error_message = "\n".join(errors)
        raise DataFrameValidationError(
            f"DataFrame validation failed with the following errors:\n{error_message}"
        )


if __name__ == "__main__":
    # Check if --examples flag is passed
    if "--examples" in sys.argv:
        ingest_sample_oh_hikes()
    ingest_oh_backpackable_hikes()
