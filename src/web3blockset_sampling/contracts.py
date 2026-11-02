"""Exact CSV contracts, independent of input columns and statistical design."""

PIPELINE_COLUMNS = [
    "sampling_unit_id", "repository", "issue_number", "artifact_type", "repository_category",
    "created_at", "closed_at", "state", "comments_count", "commits_count", "issue_title", "issue_body", "concatenated_comments",
]

METADATA_COLUMNS = [
    "sampling_unit_id", "sampling_logical_id", "sampling_repository", "sampling_source", "sampling_category",
    "sampling_original_category", "sampling_stratum", "sampling_population", "sampling_sample_size",
    "sampling_population_weight", "sampling_design_weight", "sampling_provider_weight",
    "sampling_inclusion_probability", "sampling_run_id",
]

DEFAULT_PIPELINE_SOURCES = {
    "repository": "@repository", "issue_number": "@number", "artifact_type": "@artifact_type",
    "repository_category": "repository_category", "created_at": "created_at", "closed_at": "closed_at",
    "state": "state", "comments_count": "comments_count", "commits_count": "commits_count", "issue_title": "issue_title",
    "issue_body": "issue_body", "concatenated_comments": "concatenated_comments",
}


def export_contract() -> dict:
    return {"version": "4", "occurrence_key": "sampling_unit_id",
            "pipeline_columns": list(PIPELINE_COLUMNS), "metadata_columns": list(METADATA_COLUMNS),
            "normalization": {"commits_count": "nonnegative_integer_or_empty",
                              "missing": ["blank_or_whitespace", "null_case_insensitive", "NaN"],
                              "invalid": "empty_cell_with_audit", "full_original_cells_preserved": True}}
