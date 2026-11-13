#!/bin/bash
# Helper file used by RiiviveTube for encoding to WEBM/VP8 (DONT ASK WHY BUT SOMEHOW USING THIS FILE FOR ENCODING IS FASTER)

# Copyright (C) 2026 ReviveMii Project & TheErrorExe, All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


set -u
in="${1:?input missing}"; out="${2:?output missing}"; dur="${3:-}"

FPS=30; HEIGHT=360; MINSEG=4
t0=$(date +%s.%N)
outdir=$(cd "$(dirname "$out")" && pwd) || exit 1
out="$outdir/$(basename "$out")"
[ -f "$in" ] && in="$(cd "$(dirname "$in")" && pwd)/$(basename "$in")"
tmp=$(mktemp -d "$outdir/.conv.XXXXXX") || exit 1
trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$tmp"' EXIT
[ -z "$dur" ] && dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$in")
[ -z "$dur" ] && { echo "unknown duration" >&2; exit 1; }
N=$(awk -v d="$dur" -v c="$(nproc)" -v m="$MINSEG" \
  'BEGIN{n=int(d/m); if(n>c)n=c; if(n<1)n=1; print n}')

frames=$(awk -v d="$dur" -v n="$N" -v f="$FPS" 'BEGIN{printf "%d", int(d*f/n)+1}')
seg=$(awk -v fr="$frames" -v f="$FPS" 'BEGIN{printf "%.6f", fr/f}')

pids=()
for i in $(seq 0 $((N-1))); do
  start=$(awk -v s="$seg" -v i="$i" 'BEGIN{printf "%.6f", s*i}')
  if [ "$i" -lt $((N-1)) ]; then t="-t $seg"; else t=""; fi
  ffmpeg -v error -nostdin -y -ss "$start" $t -i "$in" -an \
    -vf "fps=$FPS,scale=-2:'min($HEIGHT,ih)':flags=fast_bilinear" \
    -c:v libvpx -deadline realtime -cpu-used 16 \
    -lag-in-frames 0 -auto-alt-ref 0 -g 300 \
    -threads 1 -slices 4 -b:v 1M -crf 20 \
    "$tmp/v$i.webm" &
  pids+=($!)
done

ffmpeg -v error -nostdin -y -i "$in" -vn -map 0:a:0? \
  -c:a libvorbis -b:a 128k -ac 2 -ar 44100 "$tmp/a.ogg" 2>/dev/null &
apid=$!
fail=0
for p in "${pids[@]}"; do wait "$p" || fail=1; done
wait "$apid" 2>/dev/null
[ "$fail" -eq 1 ] && { echo "video segment failed" >&2; exit 1; }
for i in $(seq 0 $((N-1))); do echo "file 'v$i.webm'"; done > "$tmp/list.txt"

if [ -s "$tmp/a.ogg" ]; then
  maps=(-i "$tmp/a.ogg" -map 0:v -map 1:a)
else
  maps=(-map 0:v)
fi

ffmpeg -v error -nostdin -y -f concat -safe 0 -i "$tmp/list.txt" "${maps[@]}" \
  -c copy -f webm "$tmp/final.webm" || { echo "concat failed" >&2; exit 1; }

mv -f "$tmp/final.webm" "$out" || exit 1

t1=$(date +%s.%N)
awk -v t0="$t0" -v t1="$t1" -v d="$dur" -v n="$N" 'BEGIN{
  e=t1-t0
  printf "segments %d\nvideo:    %.2fs\ntime:     %.2fs\nspeed:    %.1fx\n", n, d, e, d/e
}' >&2
exit 0
