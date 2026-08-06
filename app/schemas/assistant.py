import json
import os
from pydantic import BaseModel
from typing import List, Optional


_states_path = os.path.join(os.path.dirname(__file__), "..", "data", "states.json")
with open(_states_path) as _f:
    _states_data = json.load(_f)

STATE_NAMES = {s["id"]: s["name"] for s in _states_data}
STATE_CENTROIDS = {s["id"]: (s["lat"], s["lng"]) for s in _states_data}


class ConsultationRequest(BaseModel):
    text: str
    official_type: str
    state: str = "jalisco"
    municipality: Optional[str] = None
    session_id: str = "default_session"


class ConsultationResponse(BaseModel):
    guion: str
    fundamento: List[str]
    accion: List[str]
    credits_used: int
    credits_remaining: int


class AppealRequest(BaseModel):
    situation: str
    state: str = "jalisco"
    municipality: Optional[str] = None


class StateInfo(BaseModel):
    id: str
    name: str
    available: bool


def get_available_states(available_ids: List[str]) -> List[StateInfo]:
    return [
        StateInfo(
            id=state_id,
            name=STATE_NAMES.get(state_id, state_id.title()),
            available=state_id in available_ids,
        )
        for state_id in STATE_NAMES
    ]
