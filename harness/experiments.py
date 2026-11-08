"""Experiment definitions, the one place to add more.

An experiment varies ONE instance parameter (`param`) over `values`, generating seeded instances
1..instances_per_size for every value, so every algorithm sees identical instances. `fixed`
overrides the other parameters; everything else stays at the InstanceConfig defaults. To add an
experiment, add an entry to EXPERIMENTS; the runner, aggregator and suite need no change.

`param` and the keys of `fixed` are one of PARAMS (the name -> InstanceConfig field map below).
"""
from dataclasses import dataclass, field

from .config import InstanceConfig

# Experiment parameter name -> InstanceConfig field.
PARAMS = {
    "customers": "num_customers",
    "period": "period_minutes",
    "speed": "speed_kmh",
    "departure": "departure_minute",
    "radius": "radius_km",
}


@dataclass(frozen=True)
class Experiment:
    name: str
    description: str
    param: str
    values: tuple
    instances_per_size: int
    fixed: dict = field(default_factory=dict)
    full_run_instances: int = 0  # default for the "until every place is visited" view

    def __post_init__(self):
        if self.param not in PARAMS:
            raise ValueError(f"unknown parameter {self.param!r}; known: {', '.join(PARAMS)}")
        bad = [k for k in self.fixed if k not in PARAMS or k == self.param]
        if bad:
            raise ValueError(f"fixed parameter(s) {bad} must be other known parameters")

    @property
    def sizes(self):  # the customer counts of a customers experiment (kept for older callers)
        return self.values

    def config(self, seed, value):
        """The InstanceConfig for one seed at one sweep value."""
        fields = {PARAMS[k]: v for k, v in self.fixed.items()}
        fields[PARAMS[self.param]] = value
        return InstanceConfig(seed=seed, **fields)


EXPERIMENTS = {e.name: e for e in (
    Experiment(
        name="scaling", param="customers", values=(5, 10, 15, 20, 30, 50, 100),
        instances_per_size=30, full_run_instances=10,
        description="Effect of the number of customers on every algorithm."),
    Experiment(
        name="time-budget", param="period", values=(240, 480, 720, 960, 1080),
        instances_per_size=30, fixed={"customers": 30},
        description="Effect of the length of the travel period (minutes from the 06:00 "
                    "departure) with 30 customers."),
    Experiment(
        name="speed", param="speed", values=(20, 30, 40, 60, 80),
        instances_per_size=30, fixed={"customers": 30},
        description="Effect of the travel speed (km/h) with 30 customers."),
    Experiment(
        name="window-alignment", param="departure", values=(360, 540, 720, 900, 1080),
        instances_per_size=30, fixed={"customers": 30, "period": 360},
        description="Effect of when a 6-hour period starts (departure minute since midnight), "
                    "i.e. how it lines up with the four customer time windows, with 30 customers."),
    Experiment(
        name="spread", param="radius", values=(25, 50, 100, 150, 250),
        instances_per_size=30, fixed={"customers": 20},
        description="Effect of how far customers are spread: the selection radius (km) around "
                    "the depot, with 20 customers."),
    Experiment(
        name="stress", param="customers", values=(100, 150, 200, 300),
        instances_per_size=10,
        description="Runtime growth, time-limit hits and failures at large sizes."),
)}
