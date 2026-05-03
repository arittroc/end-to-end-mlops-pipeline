"""
run_pipeline.py
===============
Convenience entry point for the ZenML House Price Prediction pipeline.

Usage
-----
    python run_pipeline.py                                    # defaults: data/indian_housing.csv, INFO logging
    python run_pipeline.py --data-path data/indian_housing.csv --log-level DEBUG
"""

import argparse

from src.pipeline import run_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the ZenML House Price Prediction pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default="data/indian_housing.csv",
        help="Path to the raw dataset (.csv or .zip).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    args = parser.parse_args()
    run_pipeline(data_path=args.data_path, log_level=args.log_level)
