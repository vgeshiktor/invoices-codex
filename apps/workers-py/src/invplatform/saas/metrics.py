from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import TypedDict


@dataclass(frozen=True)
class RequestMetricKey:
    method: str
    route: str
    status_code: int


class MetricsSnapshot(TypedDict):
    request_counts: dict[RequestMetricKey, int]
    request_duration_ms_sum: dict[tuple[str, str], float]


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._request_counts: dict[RequestMetricKey, int] = defaultdict(int)
        self._request_duration_ms_sum: dict[tuple[str, str], float] = defaultdict(float)

    def observe_http(self, method: str, route: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            key = RequestMetricKey(method=method.upper(), route=route, status_code=int(status_code))
            self._request_counts[key] += 1
            self._request_duration_ms_sum[(method.upper(), route)] += float(duration_ms)

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            return {
                "request_counts": dict(self._request_counts),
                "request_duration_ms_sum": dict(self._request_duration_ms_sum),
            }

    def render_prometheus(self) -> str:
        snap = self.snapshot()
        lines = [
            "# HELP invplatform_http_requests_total Total HTTP requests.",
            "# TYPE invplatform_http_requests_total counter",
        ]
        request_counts = snap["request_counts"]
        for key, count in sorted(
            request_counts.items(),
            key=lambda x: (x[0].method, x[0].route, x[0].status_code),
        ):
            lines.append(
                'invplatform_http_requests_total{method="%s",route="%s",status="%s"} %d'
                % (key.method, key.route, key.status_code, count)
            )

        lines.extend(
            [
                "# HELP invplatform_http_request_duration_ms_sum Sum of request duration in ms.",
                "# TYPE invplatform_http_request_duration_ms_sum counter",
            ]
        )
        duration = snap["request_duration_ms_sum"]
        for (method, route), total in sorted(duration.items(), key=lambda x: (x[0][0], x[0][1])):
            lines.append(
                'invplatform_http_request_duration_ms_sum{method="%s",route="%s"} %.3f'
                % (method, route, total)
            )
        return "\n".join(lines) + "\n"
