"""Generate an editable LTspice .asc schematic for a resistor crossbar.

Rows are driven by voltage sources; columns are held at 0 V by
zero-volt current-sensing sources. All connected nodes use LTspice FLAGs.
A positive matrix entry a maps to a resistance R_base / a.
A zero entry maps to an open circuit (no resistor).

Run: python generate_crossbar_asc.py
"""

from pathlib import Path
from math import isfinite

# Global config vars
outputDir = "./LTSpiceFiles/"
outputFileName = "crossbar.asc"
outputFilePath = outputDir + outputFileName


def generate_crossbar_asc(
    matrix,
    voltages,
    base_resistance=10_000,
    output=(outputFilePath),
):
    if not matrix or not matrix[0]:
        raise ValueError("Matrix must be nonempty.")
    rows, cols = len(matrix), len(matrix[0])
    if any(len(row) != cols for row in matrix):
        raise ValueError("Every matrix row must have the same number of columns.")
    if len(voltages) != rows:
        raise ValueError("One input voltage is required for each matrix row.")
    if not isfinite(base_resistance) or base_resistance <= 0:
        raise ValueError("Base resistance must be positive and finite.")
    if any(not isfinite(v) for v in voltages):
        raise ValueError("All input voltages must be finite.")
    if any(not isfinite(a) or a < 0 for row in matrix for a in row):
        raise ValueError("Matrix weights must be finite and nonnegative.")

    # Component pin positions for LTspice's built-in res/voltage symbol,
    # with rotation R0: upper pin (x+16, y+16), lower pin (x+16, y+96).
    lines = [
        "Version 4",
        f"SHEET 1 {max(1300, 520 + cols * 192)} {max(800, 330 + rows * 160)}",
    ]
    lines.append(
        "TEXT 64 16 Left 2 ;Resistor crossbar: matrix rows = voltage inputs, columns = current outputs"
    )
    lines.append(
        "TEXT 64 48 Left 2 ;Node labels connect identical names without long wires"
    )

    def part(symbol, x, y, name, value, upper, lower):
        pin_x = x + 16 if symbol == "res" else x

        lines.extend(
            [
                f"SYMBOL {symbol} {x} {y} R0",
                f"SYMATTR InstName {name}",
                f"SYMATTR Value {value:.12g}",
                f"FLAG {pin_x} {y + 16} {upper}",
                f"FLAG {pin_x} {y + 96} {lower}",
            ]
        )

    # Source pins: row voltage at upper pin, ground at lower pin.
    lines.append("TEXT 64 80 Left 2 ;Inputs")
    for i, voltage in enumerate(voltages, start=1):
        part("voltage", 64, 128 + (i - 1) * 160, f"V{i}", voltage, f"row{i}", "0")

    lines.append("TEXT 288 80 Left 2 ;Crossbar resistors")
    for i, row in enumerate(matrix, start=1):
        for j, weight in enumerate(row, start=1):
            if weight == 0:
                continue
            part(
                "res",
                288 + (j - 1) * 192,
                128 + (i - 1) * 160,
                f"R{i}_{j}",
                base_resistance / weight,
                f"row{i}",
                f"col{j}",
            )

    outputs_x = 288 + cols * 192 + 80
    lines.append(f"TEXT {outputs_x} 80 Left 2 ;Output current sensors")
    for j in range(1, cols + 1):
        part("voltage", outputs_x, 128 + (j - 1) * 160, f"VSENSE{j}", 0, f"col{j}", "0")

    directives_y = 180 + max(rows, cols) * 160
    lines.append(f"TEXT 64 {directives_y} Left 2 !.op")
    lines.append(
        f"TEXT 64 {directives_y+48} Left 2 ;Check negative of I(VSENSE1), etc. for positive dot products"
    )

    out = Path(output)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Created: {out.resolve()}")
    for j in range(cols):
        expected = sum(
            voltages[i] * matrix[i][j] / base_resistance for i in range(rows)
        )
        print(
            f"Column {j+1}: ideal dot-product current = {expected * 1000:.6g} mA; "
            f"LTspice I(VSENSE{j+1}) = {-expected * 1000:.6g} mA"
        )


if __name__ == "__main__":
    generate_crossbar_asc(
        matrix=[[1, 2], [3, 4]],
        voltages=[5, 6],
        base_resistance=10_000,
        output=outputFilePath,
    )
