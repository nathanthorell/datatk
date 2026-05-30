from .data_compare_normalize import (
    _find_differences_case_insensitive,
    _normalize_column_names,
    _normalize_data_types,
)
from .data_compare_types import ComparisonResult, QueryResult


def compare_dataframes(
    left: QueryResult,
    right: QueryResult,
    *,
    case_insensitive: bool = False,
    show_performance: bool = True,
) -> ComparisonResult:
    left_df = left.results.reset_index(drop=True)
    right_df = right.results.reset_index(drop=True)

    left_cols = {col.lower() for col in left_df.columns}
    right_cols = {col.lower() for col in right_df.columns}

    result = ComparisonResult(
        left=left,
        right=right,
        row_count_match=left.row_count == right.row_count,
        shape_match=left_df.shape == right_df.shape,
        columns_match=left_cols == right_cols,
        case_insensitive=case_insensitive,
        show_performance=show_performance,
    )

    if not result.columns_match:
        return result

    right_df = _normalize_column_names(left_df, right_df)
    left_df, right_df = _normalize_data_types(left_df, right_df)

    cols = sorted(left_df.columns.tolist())
    left_sorted = left_df[cols]
    right_sorted = right_df[cols]

    if case_insensitive:
        left_only, right_only, common_rows = _find_differences_case_insensitive(
            left_sorted, right_sorted
        )
    else:
        merged = left_sorted.merge(right_sorted, how="outer", indicator=True)
        left_only = merged[merged["_merge"] == "left_only"].drop(columns="_merge")
        right_only = merged[merged["_merge"] == "right_only"].drop(columns="_merge")
        common_rows = merged[merged["_merge"] == "both"].drop(columns="_merge")

    result.left_only = left_only
    result.right_only = right_only
    result.common_rows = common_rows
    result.is_equal = len(left_only) == 0 and len(right_only) == 0 and len(common_rows) > 0

    return result
