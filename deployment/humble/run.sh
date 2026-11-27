#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
image=instinct-carrybox:wall19-humble-1264316
container=(docker run --rm --pull never
    --mount "type=bind,source=$project_dir,target=/work/onboard,readonly")
policy=(python scripts/g1_carrybox.py --bundle models/carrybox_wall19 --standdir models/stand_onboard)
runtime_dir="$project_dir/.deployment/humble"

mode=${1:-offline}
case "$mode" in
    offline)
        exec "${container[@]}" --network none "$image" "${policy[@]}" --offline --steps 50
        ;;
    check)
        exec "${container[@]}" --network none -e PYTHONPATH=/work/onboard \
            -e 'CYCLONEDDS_URI=<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="lo"/></Interfaces></General></Domain></CycloneDDS>' \
            "$image" python deployment/humble/check_environment.py
        ;;
    depth-preview|dry-run|live)
        mapfile -t cameras < <(lsusb -d 8086:0b3a | awk '{sub(/:$/, "", $4); print "/dev/bus/usb/" $2 "/" $4}')
        if [[ ${#cameras[@]} -ne 1 ]]; then
            echo "Expected one RealSense D435i USB device." >&2
            exit 1
        fi
        camera=${cameras[0]}
        usb_path=$(udevadm info --query=path --name="$camera")
        camera_devices=("$camera")
        for device in /dev/video* /dev/hidraw*; do
            [[ -c "$device" ]] || continue
            device_path=$(udevadm info --query=path --name="$device") || continue
            if [[ "$device_path" == "$usb_path/"* ]]; then
                camera_devices+=("$device")
            fi
        done
        for device in "${camera_devices[@]}"; do
            container+=(--device "$device")
        done
        container+=(--mount type=bind,source=/run/udev,target=/run/udev,readonly)
        if [[ "$mode" != dry-run ]]; then
            docker image inspect "$image" >/dev/null
            running=$(docker ps --filter "ancestor=$image" --format '{{.Names}}')
            if [[ -n "$running" ]] || fuser "${camera_devices[@]}" >/dev/null 2>&1; then
                echo "A carrybox container or the D435i is already in use." >&2
                exit 1
            fi
        fi
        if [[ "$mode" == depth-preview ]]; then
            mkdir -p "$runtime_dir"
            capture_dir=$(mktemp -d "$runtime_dir/depth-preview.XXXXXX")
            chmod 755 "$capture_dir"
            printf 'Depth preview: %s\n' "$capture_dir"
            exec "${container[@]}" --network none -e PYTHONPATH=/work/onboard \
                --mount "type=bind,source=$capture_dir,target=/capture" \
                "$image" timeout 15s python deployment/humble/depth_preview.py
        fi
        dds='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="enP8p1s0"/></Interfaces></General></Domain></CycloneDDS>'
        if [[ "$mode" == live ]]; then
            factory_motion="$runtime_dir/factory-motion"
            [[ -x "$factory_motion" ]]
            "${container[@]}" --network none "$image" "${policy[@]}" --offline --steps 3
            echo "Releasing factory motion. Cold start can move the robot as soon as inputs arrive."
            timeout 25s "$factory_motion" --release
            policy+=(--nodryrun)
        fi
        exec "${container[@]}" --network host \
            -e ROS_DOMAIN_ID=0 -e "CYCLONEDDS_URI=$dds" \
            "$image" "${policy[@]}"
        ;;
    *)
        echo "Usage: $0 offline | check | depth-preview | dry-run | live" >&2
        exit 2
        ;;
esac
