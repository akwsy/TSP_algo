"""The single configuration object for instance generation."""
from dataclasses import dataclass

DAY_START = 360          # 06:00
DAY_END = 1440           # 24:00
SLOT_COUNT = 4
SLOT_MINUTES = (DAY_END - DAY_START) // SLOT_COUNT  # 270


DEFAULT_DEPARTURE = 360
DEFAULT_PERIOD = 480
DEFAULT_SPEED = 40.0


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class InstanceConfig:
    seed: int
    num_customers: int = 10
    departure_minute: int = DEFAULT_DEPARTURE
    period_minutes: int = DEFAULT_PERIOD
    speed_kmh: float = DEFAULT_SPEED

    def __post_init__(self):
        if self.seed is None:
            raise ConfigError("seed is required")
        if self.num_customers < 1:
            raise ConfigError("customers must be at least 1")
        if not 0 <= self.departure_minute <= DAY_END:
            raise ConfigError("departure must be between 0 and 1440")
        if self.period_minutes <= 0:
            raise ConfigError("period must be positive")
        if self.speed_kmh <= 0:
            raise ConfigError("speed must be positive")
        if self.departure_minute + self.period_minutes > DAY_END:
            raise ConfigError(
                f"departure ({self.departure_minute}) + period ({self.period_minutes}) "
                f"must not exceed {DAY_END}")

    @property
    def deadline_minute(self):
        return self.departure_minute + self.period_minutes

    @property
    def instance_id(self):
        """n<N>-seed<S>, plus -dep/-per/-spd for any parameter that differs from its default,
        so different problems never share an id."""
        parts = [f"n{self.num_customers}-seed{self.seed}"]
        if self.departure_minute != DEFAULT_DEPARTURE:
            parts.append(f"dep{self.departure_minute}")
        if self.period_minutes != DEFAULT_PERIOD:
            parts.append(f"per{self.period_minutes}")
        if self.speed_kmh != DEFAULT_SPEED:
            parts.append(f"spd{self.speed_kmh:g}")
        return "-".join(parts)
