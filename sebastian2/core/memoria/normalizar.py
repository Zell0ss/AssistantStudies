"""Normalizacion de alias (fase 2, plan §2.4).

Minusculas, sin tildes ni dieresis (la `ñ` se queda), sin puntuacion, espacios juntos y **un**
articulo o posesivo inicial fuera: «El coche» -> `coche`, «Mis alergias» -> `alergias`. El plural
no se toca: para eso estan los alias.
"""
import re
import unicodedata

_INICIALES = {"el", "la", "los", "las", "un", "una", "mi", "mis", "su", "sus"}
_ENIE = "ñ"


def normalizar(texto: str) -> str:
    texto = texto.lower()
    # NFD separa letra y marca; se descarta toda marca salvo la tilde de la n (ñ = n + U+0303).
    descompuesto = unicodedata.normalize("NFD", texto)
    limpio = []
    for i, c in enumerate(descompuesto):
        if unicodedata.combining(c):
            if c == "̃" and i > 0 and descompuesto[i - 1] == "n":
                limpio.append(c)
            continue
        limpio.append(c)
    texto = unicodedata.normalize("NFC", "".join(limpio))
    texto = re.sub(r"[^\w\s]|_", " ", texto)
    palabras = texto.split()
    if palabras and palabras[0] in _INICIALES and len(palabras) > 1:
        palabras = palabras[1:]
    return " ".join(palabras)
