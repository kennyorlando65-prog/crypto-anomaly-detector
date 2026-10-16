"""Daily alert digest.

A plain-text summary of what fired, grouped by severity. No email, no
webhook, no third-party service: the digest is generated on request and
returned as text, so it works on the free tier with nothing to configure.
"""

from __future__ import annotations

from datetime import UTC, datetime

from engine.detectors import AnomalyEvent

SEVERITY_LABEL = {
    "extreme": "EXTREME",
    "notable": "NOTABLE",
    "watch": "WATCH",
}


def build_digest(
    events: list[AnomalyEvent],
    window_hours: int = 24,
    generated_at: datetime | None = None,
) -> dict:
    """Build a digest of events inside the trailing window.

    Returns both a structured payload and a ready-to-read text block, so the
    UI can render either without re-deriving anything.
    """
    now = generated_at or datetime.now(UTC)
    cutoff = now.timestamp() - window_hours * 3600

    recent = [
        e
        for e in events
        if datetime.fromisoformat(e.timestamp).timestamp() >= cutoff
    ]

    order = {"extreme": 0, "notable": 1, "watch": 2}
    recent.sort(key=lambda e: (order[e.severity], e.timestamp))

    counts = {"extreme": 0, "notable": 0, "watch": 0}
    for event in recent:
        counts[event.severity] += 1

    lines: list[str] = []
    lines.append(f"Anomaly digest - last {window_hours}h")
    lines.append(f"Generated {now.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    if not recent:
        lines.append("No anomalies flagged in this window.")
    else:
        lines.append(
            f"{len(recent)} flagged: "
            f"{counts['extreme']} extreme, "
            f"{counts['notable']} notable, "
            f"{counts['watch']} watch"
        )
        lines.append("")
        for event in recent:
            stamp = event.timestamp[:10]
            lines.append(
                f"[{SEVERITY_LABEL[event.severity]}] {event.symbol} "
                f"{event.kind} on {stamp}"
            )
            lines.append(f"    {event.detail}")

    lines.append("")
    lines.append(
        "Statistical flags only. Not investment advice, and not a prediction."
    )

    return {
        "generated_at": now.isoformat(),
        "window_hours": window_hours,
        "counts": counts,
        "total": len(recent),
        "events": [e.to_dict() for e in recent],
        "text": "\n".join(lines),
    }
