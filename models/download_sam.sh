#!/usr/bin/env sh
# Download a Segment Anything checkpoint into this folder.
#   ./download_sam.sh          -> vit_b (~375 MB, fastest; the default)
#   ./download_sam.sh vit_l    -> ~1.2 GB
#   ./download_sam.sh vit_h    -> ~2.5 GB (most accurate)
# Set SAM_MODEL_TYPE / SAM_CHECKPOINT in docker-compose.yml to match.
set -e
cd "$(dirname "$0")"
case "${1:-vit_b}" in
  vit_b) file=sam_vit_b_01ec64.pth ;;
  vit_l) file=sam_vit_l_0b3195.pth ;;
  vit_h) file=sam_vit_h_4b8939.pth ;;
  *) echo "unknown model type: $1 (vit_b, vit_l or vit_h)"; exit 1 ;;
esac
url="https://dl.fbaipublicfiles.com/segment_anything/$file"
echo "Downloading $url"
if command -v curl >/dev/null 2>&1; then curl -fL -o "$file" "$url"; else wget -O "$file" "$url"; fi
echo "Saved models/$file"
