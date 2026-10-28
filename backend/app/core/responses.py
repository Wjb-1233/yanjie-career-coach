from datetime import datetime, timezone
from typing import Any


def ok(data: Any) -> dict[str, Any]:
    return {"data": data, "meta": {"timestamp": datetime.now(timezone.utc).isoformat()}}

