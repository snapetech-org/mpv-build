# Fetch a pinned Android Git dependency. A mirror is transport redundancy only:
# every successful clone must resolve to the exact commit in versions.json.
fetch_pinned_git () {
	local component=$1
	local url=$2
	local mirror=$3
	local ref=$4
	local commit=$5
	local destination=$6
	shift 6
	local source attempt head cloned
	local -a sources=("$url")
	if [ -e "$destination" ] || [ -L "$destination" ]; then
		echo >&2 "$component: refusing to fetch into existing path $destination"
		return 1
	fi

	if [ -n "$mirror" ] && [ "$mirror" != "$url" ]; then
		sources+=("$mirror")
	fi

	cloned=""
	for source in "${sources[@]}"; do
		for attempt in 1 2 3; do
			if git clone --depth 1 --branch "$ref" "$@" "$source" "$destination"; then
				cloned="$source"
				break 2
			fi
			rm -rf "$destination"
			if [ "$attempt" -lt 3 ]; then
				sleep "$attempt"
			fi
		done
		echo >&2 "$component: could not clone $source at $ref after 3 attempts"
	done

	if [ -z "$cloned" ]; then
		echo >&2 "$component: no source produced $ref"
		return 1
	fi

	if [ -n "$commit" ]; then
		head=$(git -C "$destination" rev-parse HEAD)
		if [ "$head" != "$commit" ]; then
			echo >&2 "$component: $ref from $cloned is $head, versions.json pins $commit"
			rm -rf "$destination"
			return 1
		fi
	fi
	return 0
}
