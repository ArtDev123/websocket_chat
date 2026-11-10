from enum import StrEnum


class WsClientType(StrEnum):
    JOIN = "join"
    LEAVE = "leave"
    MESSAGE = "message"
    DM = "dm"
    TYPING = "typing"


class WsServerType(StrEnum):
    SYSTEM = "system"
    MESSAGE = "message"
    DM = "dm"
    ERROR = "error"
    TYPING = "typing"
