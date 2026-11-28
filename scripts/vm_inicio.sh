#!/usr/bin/env bash
# Arranque de una VM de trabajo (lo pasa scripts/vm.sh como startup-script; corre como root en cada encendido).
# La primera vez instala todo; en los encendidos siguientes no hace nada (la VM de la clase se apaga y se vuelve a
# prender sin depender de GitHub ni de PyPI). Al terminar deja /srv/listo; si falla, el motivo queda en
#   sudo journalctl -u google-startup-scripts
#
# Qué deja:
#   /srv/dmeyf-pipeline   el repo, en la rama pedida, con .venv (Python fijado, instalado por uv, no el de la imagen)
#   /srv/datos            la carpeta de datos (config.toml apunta acá) con el crudo del curso
#   Docker + el Postgres local de docker-compose.yml (pruebas del registro y plan B)
set -euo pipefail

LISTO=/srv/listo
[ -f "$LISTO" ] && exit 0

meta() {
  curl -sf -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1" || true
}
REPO_URL="$(meta repo)";  REPO_URL="${REPO_URL:-https://github.com/MLDEVGIT/dmeyf-pipeline.git}"
RAMA="$(meta rama)";      RAMA="${RAMA:-main}"
PYTHON="$(meta python)";  PYTHON="${PYTHON:-3.12.13}"
UV_VERSION=0.13.8
CRUDO_URL="https://storage.googleapis.com/open-courses/dmeyf2026-9c6f/competencia_02_crudo.csv.gz"
DIR=/srv/dmeyf-pipeline
DATOS=/srv/datos

echo "== paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q git curl libgomp1 docker.io docker-compose-v2
systemctl enable --now docker

echo "== uv $UV_VERSION y Python $PYTHON (compartido por todos los usuarios de la VM)"
curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
export UV_PYTHON_INSTALL_DIR=/opt/uv-python

echo "== repo ($RAMA)"
git config --system --add safe.directory '*'      # el repo es de root y lo usan todos los que entran por ssh
[ -d "$DIR/.git" ] || git clone --branch "$RAMA" "$REPO_URL" "$DIR"
cd "$DIR"
uv venv --python "$PYTHON" .venv
uv pip install --python .venv/bin/python -r requirements.txt

echo "== datos y config.toml"
mkdir -p "$DATOS/competencia_02"
printf '[rutas]\ndatos = "%s"\n' "$DATOS" > config.toml
CRUDO="$DATOS/competencia_02/competencia_02_crudo.csv.gz"
[ -s "$CRUDO" ] || curl -sfL -o "$CRUDO" "$CRUDO_URL"

echo "== Postgres local"
docker compose up -d --wait

# Cualquiera que entre por ssh trabaja en /srv (docker, con sudo: los usuarios de ssh lo tienen sin clave).
chmod -R a+rwX /srv

date -u +%FT%TZ > "$LISTO"
echo "== listo"
