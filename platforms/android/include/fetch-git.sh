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
			if [[ "$ref" =~ ^[0-9a-f]{40}$ ]]; then
				# A commit pin is not a branch name. Fetch that exact object,
				# then initialize submodules at its gitlinks, never the tip's.
				if git init --quiet "$destination" \
					&& git -C "$destination" remote add origin "$source" \
					&& git -C "$destination" fetch --quiet --depth 1 origin "$ref" \
					&& git -C "$destination" checkout --quiet --detach FETCH_HEAD; then
					if [[ " $* " != *" --recurse-submodules "* ]] ||
						git -C "$destination" submodule update --init --recursive --depth 1; then
						cloned="$source"
						break 2
					fi
				fi
			elif git clone --depth 1 --branch "$ref" "$@" "$source" "$destination"; then
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
