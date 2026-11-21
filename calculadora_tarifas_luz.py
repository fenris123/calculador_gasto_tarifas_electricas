#!/usr/bin/env python3
"""Estimate electricity costs from an hourly CUPS CSV.

Assumptions:
- AE_kWh is grid energy consumed and is the billable quantity.
- Hour values are interval numbers: 1 = 00:00-01:00, 24 = 23:00-00:00.
- The 25th interval can occur on the autumn clock-change day.
- Prices supplied below are treated as tax-exclusive; only VAT is added.
- This estimates energy + contracted power only, without other bill items.
"""

import csv
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path


# CONFIGURACIÓN PARA SPYDER: edita estos valores y pulsa Run (F5).
CSV_FILENAME = "consumo_horario.csv"
SCRIPT_FOLDER = Path(__file__).resolve().parent
CSV_PATH = SCRIPT_FOLDER / CSV_FILENAME

POTENCIA_PUNTA_KW = 3.450
POTENCIA_VALLE_KW = 3.450
IVA_PORCENTAJE = 21.0


# Festivos nacionales de fecha fija dentro del periodo del CSV.
# El 6 de enero también se considera valle en 2.0TD.
HOLIDAYS = {
    date(2025, 12, 25),
    date(2026, 1, 1),
    date(2026, 1, 6),
    date(2026, 5, 1),
    date(2026, 10, 12),
}


# energy: flat o P1=punta, P2=llano, P3=valle.
# power: P1=punta, P2=valle. Precios en €/kWh y €/kW/día.
TARIFFS = {
    "eci_despreocupate": {
        "name": "Corte Inglés - Despreocúpate",
        "energy": {"flat": 0.145000},
        "power": {"P1": 0.113397, "P2": 0.113397},
        "notes": "Precios facilitados por el usuario; se aplica solo IVA.",
    },
    "eci_beneficiate": {
        "name": "Corte Inglés - Benefíciate",
        "energy": {
            "P1": 0.208289,
            "P2": 0.152992,
            "P3": 0.105240,
        },
        "power": {"P1": 0.137369, "P2": 0.089425},
        "notes": "Precios facilitados por el usuario; se aplica solo IVA.",
    },
    "octopus_relax_duo": {
        "name": "Octopus Relax Dúo",
        "energy": {"flat": 0.135},
        "power_month": {"P1": 3.60, "P2": 3.60},
        "notes": "Potencia convertida desde €/kW por 30 días a €/kW/día.",
    },
    "octopus_relax": {
        "name": "Octopus Relax",
        "energy": {"flat": 0.159},
        "power_month": {"P1": 3.60, "P2": 3.60},
        "notes": "Potencia convertida desde €/kW por 30 días a €/kW/día.",
    },
    "octopus_3": {
        "name": "Octopus 3",
        "energy": {
            "P1": 0.183,
            "P2": 0.155,
            "P3": 0.149,
        },
        "power_month": {"P1": 3.60, "P2": 3.60},
        "notes": "Potencia convertida desde €/kW por 30 días a €/kW/día.",
    },
    "iberdrola_online": {
        "name": "Iberdrola Plan Online",
        "energy": {"flat": 0.151900},
        "power": {"P1": 0.106822, "P2": 0.106822},
        "notes": (
            "Se asume que los importes son antes de IVA. "
            "Confirma si la web ya mostraba impuestos incluidos."
        ),
    },
    "masmovil_24h": {
        "name": "Masmóvil - mismo precio 24 h",
        "energy": {"flat": 0.149},
        "power": {"P1": None, "P2": None},
        "notes": (
            "Falta el precio de potencia, así que no se puede calcular "
            "el total completo. No se usa el precio de 0,190 €/kWh "
            "indicado como 'con impuestos': no coincide con añadir solo "
            "el 21% de IVA a 0,149 €/kWh."
        ),
    },
    "naturgy_por_uso": {
        "name": "Naturgy - Tarifa Por Uso Luz",
        "energy": {"flat": 0.148},
        "power": {"P1": 0.123030, "P2": 0.061562},
        "notes": (
            "Se usan los precios base facilitados. La información adicional "
            "de Naturgy menciona precios alternativos con IVA e Impuesto "
            "Eléctrico; esas cifras no se usan aquí."
        ),
    },
    "naturgy_noche": {
        "name": "Naturgy - Tarifa Noche",
        "energy": {
            "P1": 0.218,
            "P2": 0.145,
            "P3": 0.110,
        },
        "power": {"P1": 0.123030, "P2": 0.061562},
        "notes": (
            "Se usan los precios base facilitados. La información adicional "
            "de Naturgy menciona precios alternativos con IVA e Impuesto "
            "Eléctrico; esas cifras no se usan aquí."
        ),
    },
}


def parse_number(value):
    """Convierte números con coma decimal o punto decimal a float."""
    value = value.strip().replace(" ", "")

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")

    return float(value)


def parse_date(value):
    """Convierte formatos de fecha habituales a date."""
    value = value.strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).date()
    except ValueError as exc:
        raise ValueError(f"Fecha no reconocida: {value!r}") from exc


def parse_hour(value):
    """Interpreta las horas numeradas del CSV, incluidas las del cambio horario."""
    value = value.strip()

    # También acepta formatos como 00:00 o 00:00-01:00.
    match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})", value)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))

        if hour == 24 and minute == 0:
            return 23

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour

    # En este CSV: 1 = 00:00-01:00 y 24 = 23:00-00:00.
    # El intervalo 25 aparece en el domingo del cambio horario de otoño.
    bare = re.fullmatch(r"\s*(\d{1,2})\s*", value)
    if bare:
        interval = int(bare.group(1))

        if interval == 0:
            return 0
        if interval == 25:
            return 23
        if 1 <= interval <= 24:
            return interval - 1

    raise ValueError(
        f"Hora no reconocida: {value!r}. Se esperaba un intervalo entre "
        "1 y 24, o 25 en el día del cambio horario de otoño."
    )


def energy_period(day, hour):
    """Devuelve P1 punta, P2 llano o P3 valle para energía."""
    if day.weekday() >= 5 or day in HOLIDAYS:
        return "P3"

    if 10 <= hour < 14 or 18 <= hour < 22:
        return "P1"

    if 8 <= hour < 10 or 14 <= hour < 18 or 22 <= hour < 24:
        return "P2"

    return "P3"


def read_csv(path):
    """Lee Fecha, Hora y AE_kWh del CSV, permitiendo lecturas vacías."""
    raw = path.read_text(encoding="utf-8-sig")

    try:
        dialect = csv.Sniffer().sniff(raw[:8192], delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel

    rows = csv.DictReader(raw.splitlines(), dialect=dialect)

    if not rows.fieldnames:
        raise ValueError("No se pudieron leer las cabeceras del CSV.")

    field_lookup = {
        name.strip().lstrip("\ufeff").upper(): name
        for name in rows.fieldnames
    }

    required = ("FECHA", "HORA", "AE_KWH")
    missing = [name for name in required if name not in field_lookup]

    if missing:
        raise ValueError(
            "Faltan columnas requeridas: "
            + ", ".join(missing)
            + ". Se esperan Fecha, Hora y AE_kWh."
        )

    entries = []

    for line, row in enumerate(rows, start=2):
        try:
            day = parse_date(row[field_lookup["FECHA"]])
            hour = parse_hour(row[field_lookup["HORA"]])

            raw_kwh = (row[field_lookup["AE_KWH"]] or "").strip()

            if raw_kwh in ("", "<br>", "—", "-"):
                kwh = None
            else:
                kwh = parse_number(raw_kwh)

        except Exception as exc:
            raise ValueError(f"Error en la línea {line}: {exc}") from exc

        if kwh is not None and kwh < 0:
            raise ValueError(
                f"Consumo negativo en la línea {line}: {kwh}"
            )

        # Se conserva la fecha incluso si no hay lectura de energía,
        # para contar esos días en el término de potencia.
        entries.append((day, hour, kwh))

    if not entries:
        raise ValueError("El CSV no contiene filas de consumo.")

    return entries


def calculate(entries, tariff, kw_punta, kw_valle, iva_rate):
    """Calcula energía, potencia e IVA para una tarifa."""
    energy_totals = defaultdict(float)

    for day, hour, kwh in entries:
        if kwh is None:
            continue

        period = energy_period(day, hour)
        energy_totals[period] += kwh

    energy_rates = tariff["energy"]

    if "flat" in energy_rates:
        total_kwh = sum(energy_totals.values())
        rate = energy_rates["flat"]
        energy_cost = total_kwh * rate
        energy_detail = [
            ("Todas las horas", total_kwh, rate, energy_cost)
        ]
    else:
        energy_detail = []
        energy_cost = 0.0

        for period, label in (
            ("P1", "Punta"),
            ("P2", "Llano"),
            ("P3", "Valle"),
        ):
            kwh = energy_totals[period]
            rate = energy_rates[period]
            cost = kwh * rate
            energy_cost += cost
            energy_detail.append((label, kwh, rate, cost))

    # Todas las fechas del CSV cuentan para potencia, incluso si sus kWh
    # están vacíos o pendientes.
    days = len({day for day, _, _ in entries})

    power_rates = tariff.get("power")

    if power_rates is None:
        power_rates = {
            period: tariff["power_month"][period] / 30
            for period in ("P1", "P2")
        }

    power_prices_known = all(
        power_rates.get(period) is not None
        for period in ("P1", "P2")
    )

    power_cost = None

    if (
        power_prices_known
        and kw_punta is not None
        and kw_valle is not None
    ):
        power_cost = days * (
            kw_punta * power_rates["P1"]
            + kw_valle * power_rates["P2"]
        )

    subtotal = (
        energy_cost + power_cost
        if power_cost is not None
        else None
    )
    vat = subtotal * iva_rate if subtotal is not None else None
    total = subtotal + vat if subtotal is not None else None

    return {
        "energy_detail": energy_detail,
        "energy_cost": energy_cost,
        "days": days,
        "power_rates": power_rates,
        "power_cost": power_cost,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
    }


def euros(value):
    if value is None:
        return "pendiente"

    return (
        f"{value:,.2f} €"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def main():
    iva_rate = IVA_PORCENTAJE / 100

    try:
        entries = read_csv(CSV_PATH)
    except Exception as exc:
        print(f"Error leyendo {CSV_PATH}: {exc}")
        return

    days = sorted({day for day, _, _ in entries})
    total_kwh = sum(
        kwh for _, _, kwh in entries if kwh is not None
    )
    missing_kwh = sum(
        1 for _, _, kwh in entries if kwh is None
    )

    print(f"Archivo: {CSV_PATH}")
    print(
        f"Periodo de datos: {days[0]:%d/%m/%Y} a "
        f"{days[-1]:%d/%m/%Y} ({len(days)} días)"
    )
    print(f"Consumo AE_kWh: {total_kwh:.2f} kWh")
    print(
        "Intervalos sin lectura AE_kWh ignorados en energía: "
        f"{missing_kwh}"
    )
    print(
        "Los días del CSV, incluso con kWh vacíos, "
        "cuentan para el término de potencia."
    )
    print(
        f"IVA aplicado: {IVA_PORCENTAJE:.2f}% "
        "(solo IVA; no se añade Impuesto Eléctrico, "
        "alquiler de contador ni otros conceptos)"
    )

    if POTENCIA_PUNTA_KW is None or POTENCIA_VALLE_KW is None:
        print(
            "Completa POTENCIA_PUNTA_KW y POTENCIA_VALLE_KW "
            "al inicio del script para calcular la potencia."
        )
    else:
        print(
            f"Potencia contratada: punta {POTENCIA_PUNTA_KW:g} kW; "
            f"valle {POTENCIA_VALLE_KW:g} kW"
        )

    print("\nTOTALES ESTIMADOS")

    for key, tariff in TARIFFS.items():
        result = calculate(
            entries,
            tariff,
            POTENCIA_PUNTA_KW,
            POTENCIA_VALLE_KW,
            iva_rate,
        )

        print(f"\n{tariff['name']} [{key}]")

        for label, kwh, rate, cost in result["energy_detail"]:
            print(
                f"  Energía {label:12s}: {kwh:9.2f} kWh "
                f"× {rate:.6f} €/kWh = {euros(cost)}"
            )

        print(f"  Subtotal energía: {euros(result['energy_cost'])}")

        power_rates = result["power_rates"]

        if result["power_cost"] is None:
            if any(
                power_rates.get(period) is None
                for period in ("P1", "P2")
            ):
                print(
                    "  Potencia: no calculable; falta el precio "
                    "de potencia de esta tarifa."
                )
            else:
                print(
                    "  Potencia pendiente de indicar kW contratados. "
                    f"Precios P1={power_rates['P1']:.6f} y "
                    f"P2={power_rates['P2']:.6f} €/kW/día."
                )
        else:
            print(
                f"  Subtotal potencia ({result['days']} días): "
                f"{euros(result['power_cost'])}"
            )
            print(
                f"  Subtotal antes de IVA: "
                f"{euros(result['subtotal'])}"
            )
            print(
                f"  IVA ({IVA_PORCENTAJE:.2f}%): "
                f"{euros(result['vat'])}"
            )
            print(f"  TOTAL: {euros(result['total'])}")

        print(f"  Nota: {tariff['notes']}")

    print(
        "\nNota: se usa AE_kWh; "
        "no se suma AE_AUTOCONS_kWh por separado."
    )


if __name__ == "__main__":
    main()