"""Export a Wall19 checkpoint, parameters and simulation assets to one bundle."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instinct_onboard.carrybox_export import (
    DEFAULT_CHECKPOINT,
    DEFAULT_PROFILE,
    DEFAULT_SOURCE,
    DEFAULT_URDF,
    export_bundle,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=Path("models/carrybox_wall19"))
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--urdf", type=Path, default=DEFAULT_URDF)
    parser.add_argument("--physics-profile", type=Path, default=DEFAULT_PROFILE)
    args = parser.parse_args()
    print(export_bundle(args.checkpoint, args.output, args.source, args.urdf, args.physics_profile))


if __name__ == "__main__":
    main()
