import pandas as pd


def _infer_type(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if not pd.to_numeric(series, errors="coerce").isna().all():
        return "numeric"
    return "string"


def _cast_column(series: pd.Series, target: str) -> pd.Series:
    # datetime wins over object — SQL Server can return out-of-range dates as strings
    if target == "datetime":
        return pd.to_datetime(series, errors="coerce").astype("datetime64[us]")
    # numeric handles Decimal128 (Databricks/Arrow) vs float64 (pyodbc)
    if target == "numeric":
        return pd.to_numeric(series, errors="coerce")
    return series.astype(str).str.strip()


def _normalize_data_types(
    left_df: pd.DataFrame, right_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    left_out, right_out = left_df.copy(), right_df.copy()
    for col in left_df.columns:
        types = {_infer_type(left_df[col]), _infer_type(right_df[col])}
        if "datetime" in types:
            target = "datetime"
        elif "numeric" in types:
            target = "numeric"
        else:
            target = "string"
        left_out[col] = _cast_column(left_out[col], target)
        right_out[col] = _cast_column(right_out[col], target)
    return left_out, right_out


def _normalize_column_names(left_df: pd.DataFrame, right_df: pd.DataFrame) -> pd.DataFrame:
    """Return right_df with column names matched to left_df's case."""
    left_lower = {col.lower(): col for col in left_df.columns}
    col_map = {
        col: left_lower[col.lower()] for col in right_df.columns if col.lower() in left_lower
    }
    return right_df.rename(columns=col_map)


def _lowercase_strings(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].str.lower()
    return out


def _find_differences_case_insensitive(
    left: pd.DataFrame, right: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compare on lowercased data, return slices of the originals."""
    cols = left.columns.tolist()
    left_cmp = _lowercase_strings(left)
    right_cmp = _lowercase_strings(right)
    left_cmp["_row"] = range(len(left_cmp))
    right_cmp["_row"] = range(len(right_cmp))

    merged = left_cmp.merge(right_cmp, on=cols, how="outer", indicator=True, suffixes=("_l", "_r"))

    left_idx = merged.loc[merged["_merge"] == "left_only", "_row_l"].dropna().astype(int)
    right_idx = merged.loc[merged["_merge"] == "right_only", "_row_r"].dropna().astype(int)
    both_idx = merged.loc[merged["_merge"] == "both", "_row_l"].dropna().astype(int)

    return (
        left.iloc[left_idx].reset_index(drop=True),
        right.iloc[right_idx].reset_index(drop=True),
        left.iloc[both_idx].reset_index(drop=True),
    )
