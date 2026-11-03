"""Entrada compatible con la consola y la interfaz independiente de PartesTeclea."""
import sys
from pathlib import Path

if __package__ in (None, "") and not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parte_scan import motor_tecleo

if __name__ == "__main__":
    motor_tecleo.main()
else:
    sys.modules[__name__] = motor_tecleo
