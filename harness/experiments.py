"""Experiment definitions, the one place to add more.

An experiment is a name, the customer counts to vary, and how many seeded
instances to generate per size. Period, departure and speed stay at the
InstanceConfig defaults. To add an experiment, add an entry to EXPERIMENTS;
the runner and aggregator need no change.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Experiment:
    name: str
    sizes: tuple
    instances_per_size: int
    description: str = ""


EXPERIMENTS = {
    "scaling": Experiment(
        name="scaling", sizes=(5, 10, 15, 20, 30, 50, 100), instances_per_size=30,
        description="Effect of the number of customers on every algorithm."),
}
