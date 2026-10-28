"""Segundo motor de OCR (RapidOCR, local y sin internet) para cotejar los campos críticos: boleta, patente y RUT.
Es opcional: si no está instalado, ParteScan funciona igual solo con Tesseract."""
import threading

_MOTOR = None
_LOCK = threading.Lock()
_FALLO = False


def disponible():
    global _MOTOR, _FALLO
    if _MOTOR is not None:
        return True
    if _FALLO:
        return False
    with _LOCK:
        if _MOTOR is None and not _FALLO:
            try:
                from rapidocr_onnxruntime import RapidOCR
                _MOTOR = RapidOCR()
            except Exception:
                _FALLO = True
    return _MOTOR is not None


def leer(g):
    """Texto de la hoja (una línea por cuadro de texto, de arriba hacia abajo). '' si el motor no está o falla."""
    if not disponible():
        return ""
    try:
        import numpy as np
        with _LOCK:
            res, _ = _MOTOR(np.array(g.convert("RGB")))
        return "\n".join(r[1] for r in (res or []))
    except Exception:
        return ""
