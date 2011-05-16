#!/bin/bash


function display_usage {
    echo "Usage: $0 <path/to/overviewer/output>"
}

output_dir="$(readlink -f "$1")"

if [ ! -d "$output_dir" ]; then
    echo "Directory not found: ${output_dir}"
    display_usage
    exit 1
else
    echo "Working in ${output_dir}"
fi

last_ts="$(find "$output_dir" -maxdepth 1 -type d | sed -r "s~^${output_dir}/?~~" | \
    grep -Ev '^$' | sort -n | head -2 | tail -1)"
new_ts="$(date +%s)"

echo "Creating snapshot at ${new_ts} from snapshot at ${last_ts}"

cp -al "${output_dir}/${last_ts}" "${output_dir}/${new_ts}"
