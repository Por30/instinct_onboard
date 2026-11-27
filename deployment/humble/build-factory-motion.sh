#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd "$source_dir/../.." && pwd)
sdk_dir=${1:-"$HOME/unitree_sdk2-main"}
arch=$(uname -m)
third_party="$sdk_dir/thirdparty" # codespell:ignore thirdparty
dds_dir="$third_party/lib/$arch"
output_dir="$project_dir/.deployment/humble"
mkdir -p "$output_dir"
binary=$(mktemp "$output_dir/factory-motion.XXXXXX")
trap 'rm -f "$binary"' EXIT

g++ -std=c++17 -O2 -Wall -Wextra \
    -I"$sdk_dir/include" -I"$third_party/include" -I"$third_party/include/ddscxx" \
    "$source_dir/factory-motion.cpp" "$sdk_dir/lib/$arch/libunitree_sdk2.a" \
    -L"$dds_dir" -Wl,-rpath,"$dds_dir" -Wl,-rpath-link,"$dds_dir" \
    -lddscxx -lddsc -pthread -lrt -o "$binary"
chmod 755 "$binary"
"$binary" --help
mv -f "$binary" "$output_dir/factory-motion"
