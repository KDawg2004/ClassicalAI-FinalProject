"""Generate an LTspice .asc for signed vector-matrix multiplication.

Each matrix column j has two conductance paths: col{j}_pos and col{j}_neg.
For a signed weight a, G_pos=max(a, 0)/R_base and
G_neg=max(-a, 0)/R_base. Zero weights create no resistors.

Each path ends at a zero-volt sensing source (virtual ground).
With 1 volt per input unit, mathematical output y_j is
R_base * (I(VSENSE{j}P) - I(VSENSE{j}N)).

Run: python generate_differential_crossbar.py
"""

from pathlib import Path
from math import isfinite

OUTPUT_DIR = Path("./LTSpiceFiles")


def generate_differential_crossbar(
    matrix,
    voltages,
    base_resistance=10_000,
    output=OUTPUT_DIR / "crossbar_differential.asc",
):
    if not matrix or not matrix[0]:
        raise ValueError("Matrix must be nonempty")
    rows, cols = len(matrix), len(matrix[0])
    if any(len(row) != cols for row in matrix):
        raise ValueError("Matrix rows must have equal lengths")
    if len(voltages) != rows:
        raise ValueError("Each matrix row needs one voltage")
    if not isfinite(base_resistance) or base_resistance <= 0:
        raise ValueError("Base resistance must be finite and positive")
    if any(not isfinite(v) for v in voltages):
        raise ValueError("Input voltages must be finite")
    if any(not isfinite(a) for row in matrix for a in row):
        raise ValueError("Matrix entries must be finite")

    # Working LTspice R0 symbol pin offsets:
    # resistor: (x+16,y+16), (x+16,y+96)
    # voltage:  (x,y+16), (x,y+96)
    lines = [
        "Version 4",
        f"SHEET 1 {max(1400, 640 + cols * 400)} {max(900, 600 + max(rows, cols * 2) * 176 + cols * 32)}",
        "TEXT 64 16 Left 2 ;Differential crossbar: output = positive current - negative current",
        "TEXT 64 48 Left 2 ;One row input per voltage source; two grounded sense sources per output",
        "TEXT 64 80 Left 2 ;Input voltages",
        "TEXT 300 80 Left 2 ;Conductance paths (P = positive, N = negative)",
    ]

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

    for i, v in enumerate(voltages, start=1):
        part("voltage", 96, 144 + (i - 1) * 176, f"V{i}", v, f"row{i}", "0")

    # Two potential resistor positions per signed output, one for each sign.
    # Giving each sign its own column of symbols avoids overlap on schematic.
    for i, row in enumerate(matrix, start=1):
        for j, weight in enumerate(row, start=1):
            if weight == 0:
                continue  # ideal zero conductance = open circuit
            sign = "P" if weight > 0 else "N"
            x = 320 + (j - 1) * 400 + (0 if weight > 0 else 160)
            y = 144 + (i - 1) * 176
            part(
                "res",
                x,
                y,
                f"R{i}_{j}{sign}",
                base_resistance / abs(weight),
                f"row{i}",
                f"col{j}_{'pos' if weight > 0 else 'neg'}",
            )

    sensors_x = 320 + cols * 400 + 56
    lines.append(f"TEXT {sensors_x} 80 Left 2 ;Output current sensors")
    for j in range(1, cols + 1):
        part(
            "voltage",
            sensors_x,
            144 + (2 * j - 2) * 176,
            f"VSENSE{j}P",
            0,
            f"col{j}_pos",
            "0",
        )
        part(
            "voltage",
            sensors_x + 200,
            144 + (2 * j - 2) * 176,
            f"VSENSE{j}N",
            0,
            f"col{j}_neg",
            "0",
        )

    bottom = 320 + max(rows, cols * 2) * 176
    # Short, constant-input transient enables portable .meas log extraction.
    lines.append(f"TEXT 64 {bottom} Left 2 !.tran 0 1u")
    lines.append(
        f"TEXT 64 {bottom + 48} Left 2 ;Use AVG sensor currents to reconstruct signed vector results"
    )
    for j in range(1, cols + 1):
        lines.append(
            f"TEXT 64 {bottom + 96 + (j-1)*64} Left 2 !.meas TRAN IP{j} AVG I(VSENSE{j}P) FROM=0 TO=1u"
        )
        lines.append(
            f"TEXT 64 {bottom + 128 + (j-1)*64} Left 2 !.meas TRAN IN{j} AVG I(VSENSE{j}N) FROM=0 TO=1u"
        )

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Created {out.resolve()}")
    for j in range(cols):
        pos = sum(
            voltages[i] * max(matrix[i][j], 0) / base_resistance for i in range(rows)
        )
        neg = sum(
            voltages[i] * max(-matrix[i][j], 0) / base_resistance for i in range(rows)
        )
        y = (pos - neg) * base_resistance
        print(
            f"Column {j+1}: I+={pos*1000:.6g} mA, " f"I-={neg*1000:.6g} mA, y={y:.10g}"
        )
    return out


if __name__ == "__main__":
    import json

    config = json.loads(
        Path(__file__).with_name("crossbar_config.json").read_text(encoding="utf-8")
    )
    generate_differential_crossbar(
        matrix=config["matrix"],
        voltages=config["voltages"],
        base_resistance=config.get("base_resistance", 10_000),
        output=Path(__file__).with_name("crossbar_8x64.asc"),
    )
