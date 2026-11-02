"""Lay out reviewed historical ranges without estimating missing observations."""
from datetime import date


def shortlist_chart(observations):
    points = sorted(observations, key=lambda p: p.periodEnd)
    if not points:
        return None
    days = [date.fromisoformat(p.periodEnd).toordinal() for p in points]
    low, high = min(p.low for p in points), max(p.high for p in points)
    padding = max((high - low) * .15, high * .04, 1)
    floor, ceiling = max(0, low - padding), high + padding
    def y(value):
        return round(170 - (value - floor) / (ceiling - floor) * 145, 2)
    placed = []
    for p, day in zip(points, days):
        x = 350 if len(points) == 1 else round(82 + (day - days[0]) / (days[-1] - days[0]) * 518, 2)
        placed.append(dict(point=p, x=x, lowY=y(p.low), highY=y(p.high)))
    bands = []
    for a, b in zip(placed, placed[1:]):
        if a['point'].method == b['point'].method and int(b['point'].periodEnd[:4]) == int(a['point'].periodEnd[:4]) + 1:
            bands.append(' '.join(f"{p['x']},{p[k]}" for p, k in [(a, 'highY'), (b, 'highY'), (b, 'lowY'), (a, 'lowY')]))
    return dict(points=placed, bands=bands, currency=points[0].currency,
                basis=points[0].valueBasis,
                ticks=[dict(value=v, y=y(v)) for v in (ceiling, (ceiling + floor) / 2, floor)])
