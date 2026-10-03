#!/usr/bin/env bash
# Copy the database of an original coco-annotator install (MongoDB 4.0) into
# the MongoDB 7 volume used by this version. The old volume is only read.
#
#   OLD_VOLUME=coco-annotator_mongodb_data NEW_VOLUME=coco-annotator_mongodb_data_v7 \
#     ./scripts/migrate_mongo.sh
#
# Find your old volume name with: docker volume ls | grep mongodb_data
set -euo pipefail

OLD_VOLUME="${OLD_VOLUME:?set OLD_VOLUME to the existing mongo:4.0 data volume}"
NEW_VOLUME="${NEW_VOLUME:?set NEW_VOLUME to the volume the new stack will use}"
DUMP_DIR="$(pwd)/mongo-dump-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DUMP_DIR"

echo "1/3 Dumping $OLD_VOLUME with mongo:4.0 ..."
docker run -d --rm --name coco-migrate-old -v "$OLD_VOLUME":/data/db mongo:4.0 >/dev/null
trap 'docker rm -f coco-migrate-old coco-migrate-new >/dev/null 2>&1 || true' EXIT
until docker exec coco-migrate-old mongo --quiet --eval 'db.runCommand({ping:1}).ok' >/dev/null 2>&1; do sleep 1; done
docker exec coco-migrate-old mongodump --archive=/tmp/dump.archive --gzip
docker cp coco-migrate-old:/tmp/dump.archive "$DUMP_DIR/dump.archive"
docker rm -f coco-migrate-old >/dev/null

echo "2/3 Restoring into $NEW_VOLUME with mongo:7.0 ..."
docker volume create "$NEW_VOLUME" >/dev/null
docker run -d --rm --name coco-migrate-new -v "$NEW_VOLUME":/data/db mongo:7.0 >/dev/null
until docker exec coco-migrate-new mongosh --quiet --eval 'db.runCommand({ping:1}).ok' >/dev/null 2>&1; do sleep 1; done
docker cp "$DUMP_DIR/dump.archive" coco-migrate-new:/tmp/dump.archive
docker exec coco-migrate-new mongorestore --archive=/tmp/dump.archive --gzip
docker rm -f coco-migrate-new >/dev/null

echo "3/3 Done. A copy of the dump is in $DUMP_DIR"
echo "Point the 'database' service at the new volume, e.g. in docker-compose.yml:"
echo "  volumes: [\"$NEW_VOLUME:/data/db\"]   and   volumes: { $NEW_VOLUME: { external: true } }"
