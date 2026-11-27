#This file generates LTSpice schematics for a differential crossbar
#using the trained weights from the MNIST dataset and generate_corssbar_acs.

#Can be modified, but outputs 6 unique schematics(Which can be tested), one for each digit 0-5, using the first sample of each class.
import numpy as np
from pathlib import Path

from training.toyDataSet import X, y
from spiceSims.negativesIncluded.generate_corssbar_asc import (
    generate_differential_crossbar
)

# Project paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
TRAINING_DIR = PROJECT_DIR / "training"
OUTPUT_DIR = PROJECT_DIR / "spiceSims" / "LTSpiceFiles"

#Config
G_MAX = 0.001       #1 mS
R_BASE = 1 / G_MAX  #1000 ohms
V_SCALE = 0.1       #0.1 V maximum input

#load trained weights
W = np.load(TRAINING_DIR / "trained_weights.npy")

if W.shape != (64, 6):
    raise ValueError(f"Expected weight shape (64, 6), got {W.shape}")

#normalize all weights using one global maximum
W_MAX = np.max(np.abs(W))

if W_MAX == 0:
    raise ValueError("All weights are zero")

W_NORMALIZED = W / W_MAX

print(f"Largest original weight: {W_MAX:.6f}")
print(f"Maximum conductance: {G_MAX} S")
print(f"Base resistance: {R_BASE} ohms")

# Select one sample from each class
sample_indices = [
    np.flatnonzero(y == digit)[0]
    for digit in range(6)
]

# Generate one schematic per sample
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

for digit, sample_idx in enumerate(sample_indices):

    # Convert normalized pixel intensities to voltages
    input_voltages = (X[sample_idx] * V_SCALE).tolist()

    output_file = OUTPUT_DIR / f"mnist_digit_{digit}.asc"

    print(f"\nGenerating digit {digit}")
    print(f"Dataset index: {sample_idx}")

    generate_differential_crossbar(
        matrix=W_NORMALIZED.tolist(),
        voltages=input_voltages,
        base_resistance=R_BASE,
        output=output_file
    )

print("\nGenerated all six crossbar schematics.")