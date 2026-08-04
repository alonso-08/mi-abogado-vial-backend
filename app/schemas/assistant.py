from pydantic import BaseModel
from typing import List, Optional


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


class StateInfo(BaseModel):
    id: str
    name: str
    available: bool


STATE_NAMES = {
    "jalisco": "Jalisco",
    "cdmx": "Ciudad de Mexico",
    "nuevo_leon": "Nuevo Leon",
    "quintana_roo": "Quintana Roo",
    "estado_de_mexico": "Estado de Mexico",
    "puebla": "Puebla",
    "guanajuato": "Guanajuato",
    "michoacan": "Michoacan",
    "chiapas": "Chiapas",
    "veracruz": "Veracruz",
    "oaxaca": "Oaxaca",
    "sonora": "Sonora",
    "chihuahua": "Chihuahua",
    "tamaulipas": "Tamaulipas",
    "sinaloa": "Sinaloa",
    "durango": "Durango",
    "coahuila": "Coahuila",
    "nayarit": "Nayarit",
    "aguascalientes": "Aguascalientes",
    "queretaro": "Queretaro",
    "hidalgo": "Hidalgo",
    "colima": "Colima",
    "tlaxcala": "Tlaxcala",
    "morelos": "Morelos",
    "baja_california": "Baja California",
    "baja_california_sur": "Baja California Sur",
    "campeche": "Campeche",
    "tabasco": "Tabasco",
    "zacatecas": "Zacatecas",
    "guerrero": "Guerrero",
    "yucatan": "Yucatan",
}


def get_available_states(available_ids: List[str]) -> List[StateInfo]:
    return [
        StateInfo(
            id=state_id,
            name=STATE_NAMES.get(state_id, state_id.title()),
            available=state_id in available_ids,
        )
        for state_id in STATE_NAMES
    ]
