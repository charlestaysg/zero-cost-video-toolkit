#!/usr/bin/env bash
# Join the silent render and the final mix into one MP4 (H.264 copied, AAC 192 kb/s).
# Usage: ./mux.sh [video_silent.mp4] [final_mix.wav] [output.mp4]
set -euo pipefail
VIDEO="${1:-out/video_silent.mp4}"
AUDIO="${2:-out/audio/final_mix.wav}"
OUT="${3:-out/video.mp4}"
ffmpeg -v error -y -i "$VIDEO" -i "$AUDIO" -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"
ffprobe -v error -show_entries format=duration:stream=codec_type,codec_name,width,height,r_frame_rate -of compact "$OUT"
echo "wrote $OUT"
