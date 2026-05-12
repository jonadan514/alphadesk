import pandas as pd
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parents[3] / "data"


class FeatureStore:
    def __init__(self, data_dir: Path = DATA_DIR):
        self._dir = Path(data_dir)

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(self, df: pd.DataFrame, name: str) -> Path:
        self._dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.today().strftime("%Y%m%d")
        path = self._dir / f"{name}_{date_str}.parquet"
        df.to_parquet(path)
        print(f"[FeatureStore] Saved {df.shape} → {path}")
        return path

    def load(self, path: Path | str) -> pd.DataFrame:
        df = pd.read_parquet(path)
        self._validate_no_future_leak(df)
        return df

    # ------------------------------------------------------------------
    # Latest file lookup
    # ------------------------------------------------------------------

    def _latest_path(self, prefix: str) -> Path | None:
        matches = sorted(self._dir.glob(f"{prefix}_*.parquet"), reverse=True)
        return matches[0] if matches else None

    def get_latest_features(self, prefix: str = "equity_features") -> pd.DataFrame:
        path = self._latest_path(prefix)
        if path is None:
            raise FileNotFoundError(f"No parquet files matching '{prefix}_*.parquet' in {self._dir}")
        print(f"[FeatureStore] Loading {path}")
        return self.load(path)

    # ------------------------------------------------------------------
    # Leak validation
    # ------------------------------------------------------------------

    def _validate_no_future_leak(self, df: pd.DataFrame) -> None:
        """Raise if any column name contains a future-date hint or if the
        DataFrame index contains dates beyond today."""
        today = pd.Timestamp.today().normalize()

        # Index date check
        if isinstance(df.index, pd.DatetimeIndex):
            future_rows = df.index[df.index > today]
            if len(future_rows) > 0:
                raise ValueError(
                    f"[FeatureStore] Leak detected: {len(future_rows)} rows have future dates "
                    f"(first: {future_rows[0].date()})"
                )

        # Column name heuristic: column names that look like future targets
        suspicious = [c for c in df.columns if "fwd" in c.lower() or "future" in c.lower()]
        if suspicious:
            raise ValueError(
                f"[FeatureStore] Potential look-ahead columns detected: {suspicious}. "
                "Ensure these are targets only, not input features."
            )
