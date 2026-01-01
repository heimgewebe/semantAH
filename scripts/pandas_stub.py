"""A lightweight pandas stub for offline testing.

⚠️  CI/Smoke Testing Only - Not a Pandas Replacement
====================================================

This module implements a minimal subset of the pandas API for CI/smoke testing
without requiring the full pandas dependency. It is **intentionally incomplete**
and **not semantically equivalent** to pandas.

Supported operations:
- DataFrame construction from dictionaries
- Column access and assignment
- `apply`, `groupby`, and conversion to records
- `sample`, `iloc`, `reset_index` (limited implementations)

Key differences from pandas:
- `iloc[i]` returns a DataFrame, not a Series (for single integer index)
- `sample(frac=...)` uses `round()` for row count calculation
- No support for `replace` parameter in `sample()`
- Index tracking is not implemented

This stub should only be used for testing code paths, not for verifying
pandas-compatible behavior or results.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Sequence, Tuple


class Series:
    def __init__(self, values: List[Any]):
        self._values = list(values)

    def apply(self, func: Callable[[Any], Any]) -> "Series":
        return Series([func(v) for v in self._values])

    def tolist(self) -> List[Any]:
        return list(self._values)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._values)

    def __len__(self) -> int:  # pragma: no cover - convenience
        return len(self._values)

    def __getitem__(self, idx: int) -> Any:  # pragma: no cover - convenience
        return self._values[idx]


class IlocIndexer:
    """Helper class for integer-location based indexing."""

    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def __getitem__(self, key: Any) -> "DataFrame":
        """Support integer slicing like df.iloc[::-1] or df.iloc[0:5]

        Note:
            Unlike pandas, single integer indexing (e.g., df.iloc[0]) returns
            a DataFrame with one row, not a Series. This simplifies the stub
            implementation but differs from pandas behavior.
        """
        if isinstance(key, slice):
            sliced_rows = self._rows[key]
            return DataFrame(sliced_rows)
        else:
            # Single integer index with bounds checking
            if not isinstance(key, int):
                raise TypeError(
                    f"iloc indexer requires integer, not {type(key).__name__}"
                )
            if key < -len(self._rows) or key >= len(self._rows):
                raise IndexError(
                    f"index {key} is out of bounds for axis 0 with size {len(self._rows)}"
                )
            return DataFrame([self._rows[key]])


class DataFrame:
    def __init__(self, data: Iterable[Dict[str, Any]] | None = None):
        rows = [deepcopy(row) for row in (data or [])]
        self._rows: List[Dict[str, Any]] = rows
        self._columns = set()
        for row in rows:
            self._columns.update(row.keys())

    @property
    def columns(self) -> List[str]:
        return list(self._columns)

    @property
    def empty(self) -> bool:
        return len(self._rows) == 0

    def __len__(self) -> int:  # pragma: no cover - convenience
        return len(self._rows)

    def copy(self) -> "DataFrame":
        return DataFrame(deepcopy(self._rows))

    def sample(
        self,
        n: int | None = None,
        frac: float | None = None,
        random_state: int | None = None,
    ) -> "DataFrame":
        """Return a random sample of rows from the DataFrame.

        Args:
            n: Number of items to sample (default: 1 if frac is None).
            frac: Fraction of rows to sample (overrides n if provided).
            random_state: Seed for reproducible randomness.

        Note:
            This stub does not support the 'replace' parameter.
            Sampling is always without replacement.
        """
        if n is not None and frac is not None:
            raise ValueError("Cannot specify both n and frac")

        if frac is not None:
            if frac < 0:
                raise ValueError("frac must be non-negative")
            if frac > 1:
                raise ValueError("frac must be <= 1")
            n = round(len(self._rows) * frac)
        if n is None:
            n = 1

        # Clamp n to valid range
        n = min(max(0, n), len(self._rows))

        # Create a shuffled copy using the random state
        rng = random.Random(random_state)
        indices = list(range(len(self._rows)))
        rng.shuffle(indices)
        sampled_rows = [self._rows[i] for i in indices[:n]]
        return DataFrame(sampled_rows)

    def reset_index(self, drop: bool = False) -> "DataFrame":
        """Reset the index of the DataFrame.

        Note:
            In this stub, index is not tracked, so this method simply
            returns a copy of the DataFrame. The 'drop' parameter is
            accepted for API compatibility but has no effect.
        """
        return self.copy()

    @property
    def iloc(self) -> "IlocIndexer":
        """Integer-location based indexing for selection by position."""
        return IlocIndexer(self._rows)

    def __getitem__(self, key: str) -> Series:
        return Series([row.get(key) for row in self._rows])

    def __setitem__(self, key: str, value: Any) -> None:
        self._columns.add(key)
        if isinstance(value, Series):
            values = value.tolist()
        elif isinstance(value, (list, tuple)):
            values = list(value)
        else:
            values = [value for _ in self._rows]

        if len(values) != len(self._rows):
            raise ValueError("Length mismatch during assignment")

        for row, val in zip(self._rows, values):
            row[key] = val

    def apply(self, func: Callable[[Dict[str, Any]], Any], axis: int = 0) -> List[Any]:
        if axis != 1:
            raise NotImplementedError("Only axis=1 is supported in this stub")
        return [func(deepcopy(row)) for row in self._rows]

    def groupby(self, keys: Sequence[str]):
        grouping: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
        for row in self._rows:
            grouping[tuple(row.get(k) for k in keys)].append(row)
        return GroupBy(grouping)

    def to_dict(self, orient: str = "records") -> List[Dict[str, Any]]:
        if orient != "records":  # pragma: no cover - unused modes
            raise NotImplementedError("Only orient='records' is supported")
        return [deepcopy(row) for row in self._rows]

    # Minimal persistence helpers for tests that exercise parquet IO.
    def to_parquet(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict()), encoding="utf-8")


class GroupBy:
    def __init__(self, groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]]):
        self._groups = groups

    def __getitem__(self, key: Tuple[Any, ...]) -> DataFrame:  # pragma: no cover
        return DataFrame(self._groups[key])

    def items(self):  # pragma: no cover - convenience
        for key, rows in self._groups.items():
            yield key, DataFrame(rows)

    def __iter__(self) -> Iterator[Tuple[Tuple[Any, ...], DataFrame]]:
        for key, rows in self._groups.items():
            yield key, DataFrame(rows)


# Minimal Timestamp for isinstance checks in _normalise_meta_value
class Timestamp(datetime):
    pass


def read_parquet(path: str | Path) -> DataFrame:
    data = Path(path).read_text(encoding="utf-8")
    try:
        records = json.loads(data)
    except json.JSONDecodeError as exc:  # pragma: no cover - invalid input
        raise ValueError(f"Invalid parquet stub data: {exc}") from exc
    if not isinstance(records, list):  # pragma: no cover - invalid input
        raise ValueError("Expected list of records")
    return DataFrame(records)


__all__ = ["DataFrame", "Series", "Timestamp", "read_parquet"]
