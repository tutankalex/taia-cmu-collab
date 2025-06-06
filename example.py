import os
import subprocess
from io import StringIO

import numpy as np
import pandas as pd


def generate_netlist(
    model_name: str,
    model_type: str,
    pre_setup: str,
    temperature: float,
    length: float,
    width: float,
    body_setup: str,
) -> str:
    return f"""\
* auto-generated simulation
.model {model_name} {model_type} level=54 version=4.8.2

{pre_setup}

.temp {temperature}

* Terminal bias setup
Vgs G S 0      ; Gate-to-Source voltage
Vds D S 0      ; Drain-to-Source voltage
Vbs B S 0      ; Bulk-to-Source voltage
Vs  S 0 0      ; Source to ground (0V reference)

M1 D G S B {model_name} L={length}u W={width}u


.option GMIN=1e-15

{body_setup}

.end
"""


def run_ngspice(netlist_str: str, verbosity_level: int = 0) -> pd.DataFrame:
    """Run ngspice and return the output as a DataFrame."""
    try:
        # Execute ngspice command with stdin/stdout
        result = subprocess.run(
            "ngspice -b -D ngbehavior=hs",
            input=netlist_str.encode(),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2,
        )

        # Process stderr
        stderr = result.stderr.decode("utf-8")
        if stderr and verbosity_level > 0:
            print("[WARNING] NGSPICE Warning:")
            print(stderr)

        if result.returncode != 0:
            raise Exception("Ngspice command failed")

        # Parse the output
        stdout = result.stdout.decode("utf-8")
        lines = stdout.splitlines()

        # Find the first data block
        data_start = None
        for i, line in enumerate(lines):
            if line.startswith("Index"):
                data_start = i
                break

        if data_start is None:
            raise Exception("No data found in ngspice output")

        # Get column names from header
        header = lines[data_start].split()
        # Skip the separator line
        data_start += 2

        # Collect all data rows
        data_rows = []
        for line in lines[data_start:]:
            # Stop when we hit a non-data line
            if not line.strip() or not line[0].isdigit():
                continue
            # Split on whitespace and convert to float
            values = [float(x) for x in line.split()]
            data_rows.append(values)

        # Create DataFrame
        df = pd.DataFrame(data_rows, columns=header)
        return df

    except subprocess.TimeoutExpired:
        print("ngspice command timed out")
        raise
    except Exception as e:
        print(f"An error occurred: {e}")
        raise


def add_noise_to_current(df: pd.DataFrame, noise_level: float = 0.01) -> pd.DataFrame:
    """Add Gaussian noise to the current values while preserving voltage values."""
    df_noisy = df.copy()
    # Add noise only to current columns (i(vds))
    # Use relative noise to preserve order of magnitude
    noise = np.random.normal(0, noise_level, size=len(df))
    df_noisy["i(vds)"] = df_noisy["i(vds)"] * (1 + noise)
    return df_noisy


if __name__ == "__main__":
    # Example BSIM parameters
    params = {
        "vth0": 0.7,
        "u0": 400,
        "vsat": 1e5,
        "rdsw": 100,
        "nfactor": 1.0,
        "cdsc": 0.0,
        "cdscb": 0.0,
        "cdscd": 0.0,
        "cit": 0.0,
        "eta0": 0.0,
        "etab": 0.0,
        "dsub": 0.0,
        "k1": 0.0,
        "k2": 0.0,
        "k3": 0.0,
        "k3b": 0.0,
        "w0": 0.0,
        "dvt0": 0.0,
    }

    params_string = "\n".join([f"+{k}={v}" for k, v in params.items()])

    body = """
.control

set numdgt=16
set width=1e3
set height=1e12
set noprintscale

alter Vbs 0
dc Vds 0 1.65 0.05 Vgs 0 1.5 0.3
print V(D) V(G) V(B) I(Vds)

alter Vbs -0.75
dc Vds 0 1.65 0.05 Vgs 0 1.5 0.3
print V(D) V(G) V(B) I(Vds)

alter Vds 0.1
dc Vgs -0.5 1.65 0.01 Vbs -1.5 0 0.3
print V(D) V(G) V(B) I(Vds)

alter Vds 1.5
dc Vgs -0.5 1.65 0.01 Vbs -1.5 0 0.3
print V(D) V(G) V(B) I(Vds)

.endc
"""
    netlist = generate_netlist(
        model_name="my_nmos",
        model_type="nmos",
        pre_setup=params_string,
        temperature=27.0,
        length=10.0,
        width=10.0,
        body_setup=body,
    )
    reference_df = run_ngspice(netlist)

    # Add noise to the current data
    noisy_df = add_noise_to_current(reference_df, noise_level=0.01)

    # Print the result
    print("\nReference DataFrame:")
    print(reference_df)
    print("\nNoisy DataFrame:")
    print(noisy_df)

