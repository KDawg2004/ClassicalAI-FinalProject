"""Generate a signed crossbar ASC, batch-simulate it with LTspice, save vector.

Windows: python run_crossbar.py --ltspice "C:\\Program Files\\ADI\\LTspice\\LTspice.exe"
Requires generate_differential_crossbar.py in this directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from generate_differential_crossbar import (
    generate_differential_crossbar,
)


# Some LTspice builds use Windows-1252 for logs, others UTF-16.
def read_log(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if b"\x00" in data[:100]:
        return data.decode("utf-16-le")
    return data.decode("utf-8", errors="replace")


def parse_sense_currents(log: str, count: int) -> list[dict]:
    """Find source-current rows under the 'Operating Point' section."""
    results = []
    for j in range(1, count + 1):
        pair = {}
        for sign in ("P", "N"):
            # Example: I(VSENSE1P):  0.0005  device_current
            pattern = rf"(?im)^\s*I\(VSENSE{j}{sign}\)\s*:\s*([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\b"
            matches = re.findall(pattern, log)
            if len(matches) != 1:
                raise ValueError(
                    f"Expected exactly one I(VSENSE{j}{sign}) in LTspice log, "
                    f"found {len(matches)}. Check .op run and source names."
                )
            pair[sign] = float(matches[0])
        results.append(
            {
                "column": j,
                "current_positive_A": pair["P"],
                "current_negative_A": pair["N"],
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="crossbar_config.json",
        help="JSON with matrix, voltages, base_resistance",
    )
    parser.add_argument(
        "--ltspice",
        help="Path to LTspice.exe (optional if installed in typical location)",
    )
    parser.add_argument(
        "--outdir",
        default="results",
        help="Directory for schematic, log, and output files",
    )
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    matrix = config["matrix"]
    voltages = config["voltages"]
    base = float(config.get("base_resistance", 10000))
    if not matrix or len(voltages) != len(matrix):
        raise ValueError("Matrix must be nonempty, with one input voltage per row")
    if not all(math.isfinite(float(x)) for x in voltages):
        raise ValueError("Voltages must be finite")
    ncols = len(matrix[0])
    output_dir = Path(args.outdir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    asc = output_dir / "crossbar_differential.asc"
    generate_differential_crossbar(
        matrix=matrix, voltages=voltages, base_resistance=base, output=asc
    )

    candidates = (
        [Path(args.ltspice)]
        if args.ltspice
        else [
            Path(r"C:\Program Files\ADI\LTspice\LTspice.exe"),
            Path(r"C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe"),
            Path(r"C:\Program Files\ADI\LTspice\XVIIx64.exe"),
        ]
    )
    exe = next((p for p in candidates if p.is_file()), None)
    if exe is None:
        raise FileNotFoundError(
            "Cannot find LTspice. Supply --ltspice with its full Windows executable path."
        )

    log_path = asc.with_suffix(".log")
    if log_path.exists():
        log_path.unlink()  # Don't accidentally parse an older run!

    cmd = [str(exe), "-b", "-Run", str(asc)]
    print("Running:", subprocess.list2cmdline(cmd))
    proc = subprocess.run(
        cmd, capture_output=True, text=True, errors="replace", timeout=args.timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"LTspice exited {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"
        )
    if not log_path.exists():
        raise RuntimeError(
            f"LTspice did not produce {log_path}. Check the generated ASC, "
            "the batch command for your LTspice version, and whether a .log was generated elsewhere."
        )
    log = read_log(log_path)
    if re.search(r"(?im)^\s*(fatal error|unknown subcircuit|error:)\b", log):
        raise RuntimeError(f"LTspice reported an error; inspect {log_path}")

    measurements = parse_sense_currents(log, ncols)
    for m in measurements:
        m["output"] = base * (m["current_positive_A"] - m["current_negative_A"])
    vector = [m["output"] for m in measurements]
    expected = [
        sum(float(voltages[i]) * float(matrix[i][j]) for i in range(len(matrix)))
        for j in range(ncols)
    ]
    error = [vector[j] - expected[j] for j in range(ncols)]
    data = {
        "input_vector": voltages,
        "matrix": matrix,
        "base_resistance_ohms": base,
        "output_vector": vector,
        "expected_vector": expected,
        "error_vector": error,
        "measurements": measurements,
        "schematic": str(asc),
        "log": str(log_path),
    }
    (output_dir / "output_vector.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "output_vector.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.writer(f)
        w.writerow([f"y{j}" for j in range(1, ncols + 1)])
        w.writerow(vector)
    print("\nLTspice vector: ", vector)
    print("Expected vector:", expected)
    print("Error vector:   ", error)
    print("Saved:", output_dir / "output_vector.json")
    print("Saved:", output_dir / "output_vector.csv")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
