# calculador_gasto_tarifas_electricas
Este script nos indica cuanto habriamos consumido durante el ultimo año con las distintas tarifas electricas  de distintas compañias.
# AVISO:  Los precios en el script son de tarifas a fecha 21/11/2026.
evidentemente, deben de ser actualizados si vas a emplearlo


Comparador de tarifas eléctricas con tu consumo horario

Este proyecto calcula cuánto habrías pagado con distintas tarifas usando tu consumo eléctrico hora a hora. El cálculo se ejecuta localmente en tu ordenador: el script no sube el CSV a ningún servicio.

> **Aviso sobre los precios:** las tarifas que vienen cargadas en el script son las facilitadas y vigentes a fecha de **21 de noviembre de 2026**. Pueden haber cambiado desde entonces. Comprueba siempre los precios actuales de cada comercializadora antes de comparar o contratar.

## Qué necesitas

- Python instalado. Puedes ejecutar el archivo desde Spyder.
- La curva horaria de consumo de aproximadamente un año (idealmente, 365 días completos).
- El precio actual de cada tarifa que quieras comparar y las potencias contratadas en punta y valle.

El CSV debe estar en la misma carpeta que el script y llamarse exactamente:

```
consumo_horario.csv
```

Si el archivo descargado tiene otro nombre, renómbralo o cambia `CSV_FILENAME` al principio de `calculadora_tarifas_luz.py`. Puedes mover la carpeta completa a otra ubicación: el script busca el CSV junto al propio `.py`.

## Cómo descargar tu curva de consumo

La **distribuidora** es la empresa responsable de la red y del contador de tu zona; no tiene por qué ser la misma empresa que te vende la luz. En una factura suele aparecer el nombre de la distribuidora.

### Desde Datadis

1. Entra en [datadis.es](https://datadis.es/) y accede o crea una cuenta con los datos del titular del suministro.
2. Abre **Mis suministros** y selecciona el CUPS de la vivienda.
3. Pulsa la opción de descarga del suministro.
4. Selecciona **Datos de consumos (en kWh)**, formato **CSV** y un rango de fechas de un año.
5. Pulsa **Preparar descarga**. Cuando esté lista, descárgala desde el centro de descargas o desde el enlace que te facilite Datadis.

Los nombres de los botones pueden variar si cambia la web. Datadis permite consultar datos de suministros conectados a las distribuidoras participantes ([Datadis](https://datadis.es/)).

### Desde la web de tu distribuidora

1. Identifica la distribuidora en tu factura o en la información del punto de suministro.
2. Entra en su área de clientes. Si no tienes cuenta, regístrate como titular o sigue el proceso de autorización que solicite.
3. Busca una sección llamada **Consumo**, **Consumo horario**, **Curva de carga** o similar.
4. Elige el periodo de un año y descarga los datos en CSV con resolución horaria.

Si la web solo permite descargar varios meses cada vez, descarga todos los tramos que cubran el año y combínalos en un único CSV, quitando cualquier fila duplicada.

## Formato que lee el script

El script busca estas columnas, sin distinguir mayúsculas y minúsculas:

| Columna | Contenido |
|---|---|
| `Fecha` | Fecha de cada lectura |
| `Hora` | Número del intervalo horario: `1` a `24`; puede aparecer `25` el día del cambio al horario de invierno |
| `AE_kWh` | Energía activa consumida en ese intervalo, en kWh |

Puede haber otras columnas, por ejemplo CUPS, vertidos o autoconsumo; el cálculo no las usa. Las lecturas `AE_kWh` vacías se ignoran para el coste de energía. Las fechas de esas filas sí cuentan para el término de potencia.

Algunas distribuidoras y Datadis pueden entregar cabeceras o formatos distintos. Si el CSV no tiene `Fecha`, `Hora` y `AE_kWh`, hay que adaptar el mapeo de columnas en la función `read_csv` del script. No sustituyas los datos vacíos por cero manualmente.

## Configuración antes de ejecutar

Al principio de `calculadora_tarifas_luz.py`, revisa:

```python
CSV_FILENAME = "consumo_horario.csv"
POTENCIA_PUNTA_KW = 3.450
POTENCIA_VALLE_KW = 3.450
IVA_PORCENTAJE = 21.0
```

Escribe las potencias que aparecen en tu contrato (buscalas en tu factura, en la parte donde ponga "termino de potencia" o "potencia contratada"). Python usa punto decimal. 
Si las potencias de punta y valle son diferentes, introduce cada una en su variable.

Después abre el `.py` en Spyder y pulsa **Run (F5)**. El resultado aparece en la consola de Spyder.

## Cómo cambiar los precios de las tarifas

Las tarifas están agrupadas en el diccionario `TARIFFS`, al principio del script. Cambia los números por los precios que quieras comparar; no cambies los nombres de las claves (`energy`, `power`, `power_month`, `flat`, `P1`, `P2`, `P3`).

- **Energía a un precio fijo todo el día:** cambia el valor de `"flat"` en `"energy"`.
- **Energía con tres periodos:** `P1` es punta, `P2` llano y `P3` valle.
- **Potencia diaria:** en `"power"`, `P1` es punta y `P2` valle; los importes son €/kW/día.
- **Potencia mensual calculada para 30 días:** usa `"power_month"`; el script divide esos importes entre 30.

Ejemplo de tarifa con tres precios de energía y dos de potencia:

```python
"mi_tarifa": {
    "name": "Mi tarifa",
    "energy": {"P1": 0.20, "P2": 0.15, "P3": 0.11},
    "power": {"P1": 0.12, "P2": 0.06},
    "notes": "Precios comprobados el 21/11/2026.",
},
```

Los precios cargados se consideran antes de IVA y el programa añade el porcentaje indicado en `IVA_PORCENTAJE`. Si un precio ya incluye IVA, no lo introduzcas como si fuera antes de impuestos o el IVA quedaría duplicado. El cálculo solo añade IVA; no añade Impuesto Eléctrico, alquiler de contador, servicios adicionales ni compensación por excedentes.

Masmóvil no tendrá un total completo hasta que añadas su precio de potencia. Comprueba también las notas de cada tarifa: algunas cifras facilitadas se describieron como precios “con impuestos”.

## Periodos horarios y festivos

El script aplica el calendario horario 2.0TD de España peninsular: energía en punta, llano y valle; potencia en punta y valle. Sábados, domingos y festivos nacionales configurados se tratan como valle durante todo el día. La lista `HOLIDAYS` incluye las fechas correspondientes al periodo de datos de este repositorio.

Si usas datos de otro año o de otra zona tarifaria, revisa y actualiza `HOLIDAYS` y la clasificación de periodos de las funciones `energy_period` y `power_periods`.

## Alcance del resultado

El resultado es una estimación de energía más potencia contratada, con IVA. No reproduce todos los conceptos de una factura real: deja fuera el Impuesto Eléctrico, el alquiler del contador, servicios adicionales, descuentos, compensación de excedentes y posibles cambios de precio o impuestos durante el año.

