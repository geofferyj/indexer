from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

StrInt = Annotated[
    int,
    PlainSerializer(lambda x: f"{x}", return_type=str, when_used="json"),
]


HexInt = Annotated[
    int,
    BeforeValidator(
        lambda x: int(x, 16) if isinstance(x, str) and x.startswith("0x") else x
    ),
]
