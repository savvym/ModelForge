#!/bin/sh
set -eu

: "${S3_CORS_ALLOWED_ORIGINS:=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8081,http://127.0.0.1:8081}"

until mc alias set local http://rustfs:9000 "$S3_ACCESS_KEY_ID" "$S3_SECRET_ACCESS_KEY" >/dev/null 2>&1; do
  echo "waiting for rustfs..."
  sleep 2
done

CORS_FILE="$(mktemp)"
trap 'rm -f "$CORS_FILE"' EXIT

{
  echo "<CORSConfiguration>"
  echo "  <CORSRule>"
  globbing_was_disabled=0
  case $- in
    *f*) globbing_was_disabled=1 ;;
  esac
  set -f
  OLD_IFS=$IFS
  IFS=','
  for origin in $S3_CORS_ALLOWED_ORIGINS; do
    if [ -n "$origin" ]; then
      printf '    <AllowedOrigin>%s</AllowedOrigin>\n' "$origin"
    fi
  done
  IFS=$OLD_IFS
  if [ "$globbing_was_disabled" -eq 0 ]; then
    set +f
  fi
  cat <<'EOF'
    <AllowedMethod>GET</AllowedMethod>
    <AllowedMethod>HEAD</AllowedMethod>
    <AllowedMethod>PUT</AllowedMethod>
    <AllowedHeader>*</AllowedHeader>
    <ExposeHeader>ETag</ExposeHeader>
    <MaxAgeSeconds>3600</MaxAgeSeconds>
EOF
  echo "  </CORSRule>"
  echo "</CORSConfiguration>"
} >"$CORS_FILE"

for bucket in \
  "$S3_BUCKET_MAIN"
do
  mc mb --ignore-existing "local/$bucket"
  mc cors set "local/$bucket" "$CORS_FILE"
done

echo "rustfs buckets initialized"
