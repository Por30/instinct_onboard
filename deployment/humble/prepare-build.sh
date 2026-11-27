#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd "$source_dir/../.." && pwd)
context=${1:-"$project_dir/.deployment/humble/build-context"}
mkdir -p "$context"
cp "$source_dir"/{Dockerfile,entrypoint.sh,sources.txt} "$context/"

while read -r name revision; do
    case "$name" in
        unitree_ros2) repository=unitreerobotics/unitree_ros2 ;;
        ros2_numpy) repository=Box-Robotics/ros2_numpy ;;
        g1_crc) repository=ZiwenZhuang/g1_crc ;;
        *) echo "Unknown build source: $name" >&2; exit 1 ;;
    esac
    curl --fail --silent --show-error --location --retry 2 \
        "https://codeload.github.com/$repository/tar.gz/$revision" \
        -o "$context/$name.tar.gz"
done < "$source_dir/sources.txt"

printf 'Build context: %s\n' "$context"
