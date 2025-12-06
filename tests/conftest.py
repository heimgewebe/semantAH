import os
import sys

try:
    import pandas  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    from scripts import pandas_stub

    sys.modules.setdefault("pandas", pandas_stub)

try:
    from hypothesis import settings
    from hypothesis.errors import InvalidArgument
except Exception:  # pragma: no cover - hypothesis optional in some environments
    settings = None
else:
    try:
        settings.register_profile(
            "ci",
            settings(max_examples=100, deadline=None, derandomize=True),
        )
    except InvalidArgument:
        # Profile bereits gesetzt (z. B. bei mehrfacher Test-Session)
        pass
    settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))
