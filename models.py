from dataclasses import dataclass


@dataclass(frozen=True)
class Player:
    id: int
    name: str
    active: int
    team: str
    gender: str


@dataclass(frozen=True)
class ScheduleWindow:
    id: int
    title: str
    start_date: str
    end_date: str
    submission_open: int
    public_token: str
    created_at: str


@dataclass(frozen=True)
class PracticeSlot:
    id: int
    schedule_window_id: int
    date: str
    start_time: str
    end_time: str
    location: str
