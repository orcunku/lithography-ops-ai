"""Business-value calculator (clearly hypothetical, all inputs adjustable).

Implements the formula from the project summary:

    annual_value = incidents_avoided
                 * downtime_hours_avoided_per_incident
                 * value_per_equipment_hour
                 - operating_cost

Nothing here is presented as real ASML customer economics. Every input is a
labelled assumption the user can change.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from lithoops.config import BUSINESS


@dataclass
class ValueInputs:
    incidents_avoided_per_year: float = 12.0
    downtime_hours_avoided_per_incident: float = BUSINESS.downtime_hours_per_incident
    value_per_equipment_hour: float = BUSINESS.value_per_equipment_hour
    operating_cost_annual: float = BUSINESS.operating_cost_annual


def compute_value(inp: ValueInputs | None = None) -> dict:
    inp = inp or ValueInputs()
    gross = (inp.incidents_avoided_per_year
             * inp.downtime_hours_avoided_per_incident
             * inp.value_per_equipment_hour)
    net = gross - inp.operating_cost_annual
    return {
        "inputs": asdict(inp),
        "gross_annual_value": round(gross, 2),
        "operating_cost_annual": round(inp.operating_cost_annual, 2),
        "net_annual_value": round(net, 2),
        "disclaimer": ("Hypothetical illustration only. Not real ASML or "
                       "customer financial data."),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(compute_value(), indent=2))
