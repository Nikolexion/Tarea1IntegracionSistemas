from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import Depends, Query

from app.api.esquemas import Enlace


@dataclass(frozen=True)
class Pagina:
    limit: int
    offset: int


def _parametros_pagina(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagina:
    return Pagina(limit=limit, offset=offset)


ParametrosPagina = Annotated[Pagina, Depends(_parametros_pagina)]


def sobre_pagina(items: list[Any], total: int, pagina: Pagina, ruta: str) -> dict[str, Any]:
    def enlace(offset: int) -> Enlace:
        consulta = urlencode({"limit": pagina.limit, "offset": offset})
        return Enlace(href=f"{ruta}?{consulta}", method="GET")

    enlaces = {"self": enlace(pagina.offset)}
    if pagina.offset + pagina.limit < total:
        enlaces["siguiente"] = enlace(pagina.offset + pagina.limit)
    if pagina.offset > 0:
        # max(..., 0): si el offset no era múltiplo de limit, la anterior empieza en 0.
        enlaces["anterior"] = enlace(max(pagina.offset - pagina.limit, 0))
    return {
        "items": items, "total": total, "limit": pagina.limit, "offset": pagina.offset,
        "_links": enlaces,
    }
