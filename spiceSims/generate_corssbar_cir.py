from pathlib import Path


def generate_crossbar(matrix, voltages, base_resistance=10_000, output="crossbar.cir"):
    """Generate a resistor crossbar for positive matrix values and DC inputs."""
    if not matrix or not matrix[0] or len(matrix) != len(voltages):
        raise ValueError("One input voltage is required per matrix row.")
    cols = len(matrix[0])
    if any(len(row) != cols for row in matrix):
        raise ValueError("All matrix rows must have the same length.")
    if base_resistance <= 0 or any(value < 0 for row in matrix for value in row):
        raise ValueError("Base resistance must be positive; matrix entries must be nonnegative.")

    lines = ["* Generated resistor crossbar", "* Inputs"]
    for i, voltage in enumerate(voltages, start=1):
        lines.append(f"V{i} row{i} 0 DC {voltage:.12g}")

    lines += ["", "* Crossbar cells: R = base_resistance / matrix_value"]
    for i, row in enumerate(matrix, start=1):
        for j, value in enumerate(row, start=1):
            if value > 0:  # Zero matrix weight corresponds to an open circuit.
                lines.append(f"R{i}_{j} row{i} col{j} {base_resistance / value:.12g}")

    lines += ["", "* Zero-volt current sensors hold each output at virtual ground"]
    for j in range(1, cols + 1):
        lines.append(f"VSENSE{j} col{j} 0 DC 0")

    lines += ["", ".op", ".end"]
    Path(output).write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Expected ideal column currents, with V in volts and R in ohms.
    expected = [sum(voltages[i] * matrix[i][j] / base_resistance
                    for i in range(len(matrix))) for j in range(cols)]
    print(f"Created {output}")
    for j, current in enumerate(expected, start=1):
        print(f"Column {j}: {-current * 1000:.6g} mA at I(VSENSE{j}) "
              f"(dot-product magnitude {current * 1000:.6g} mA)")


if __name__ == "__main__":
    generate_crossbar(
        matrix=[[1, 2], [3, 4]],
        voltages=[5, 6],
        base_resistance=10_000,
    )
