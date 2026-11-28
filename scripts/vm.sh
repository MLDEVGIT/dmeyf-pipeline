#!/usr/bin/env bash
# VM de trabajo a pedido: una n2-highmem-8 STANDARD (no spot) que se crea, se usa y se borra.
#
#   bash scripts/vm.sh crear  <nombre> [rama]     crea la VM, espera a que se instale y corre las pruebas en ella
#   bash scripts/vm.sh entrar <nombre> [comando]  ssh por IAP (con comando, lo corre en /srv/dmeyf-pipeline)
#   bash scripts/vm.sh borrar <nombre>
#   bash scripts/vm.sh lista
#
# La instalación la hace scripts/vm_inicio.sh dentro de la VM: repo en la rama pedida (por defecto, la actual),
# Python fijado con uv, dependencias, config.toml apuntando a /srv/datos, el crudo del curso y el Postgres local.
# La rama tiene que estar en GitHub: la VM la clona del repo público.
# La VM corre con la cuenta de servicio dmeyf-vm (scripts/nube_crear.sh), no con la cuenta por defecto.
set -euo pipefail

PROYECTO="${DMEYF_PROYECTO:-proj-uba-261012163242176}"
ZONA="${DMEYF_ZONA:-northamerica-northeast2-c}"      # la misma zona que la instancia de Cloud SQL
TIPO="${DMEYF_TIPO_VM:-n2-highmem-8}"
DISCO_GB=100
REPO="https://github.com/MLDEVGIT/dmeyf-pipeline.git"
CUENTA_VM="dmeyf-vm@${PROYECTO}.iam.gserviceaccount.com"
ESPERA_MAX_S=1200
AQUI="$(cd "$(dirname "$0")" && pwd)"

gc() { gcloud --project="$PROYECTO" --quiet "$@"; }
ssh_vm() { local n="$1"; shift; gc compute ssh "$n" --zone="$ZONA" --tunnel-through-iap -- "$@"; }

uso() { sed -n '2,8p' "$0"; exit 2; }
[ $# -ge 1 ] || uso
ACCION="$1"; shift

case "$ACCION" in
  crear)
    [ $# -ge 1 ] || uso
    NOMBRE="$1"
    RAMA="${2:-$(git -C "$AQUI/.." rev-parse --abbrev-ref HEAD)}"
    if ! git ls-remote --exit-code --heads "$REPO" "$RAMA" >/dev/null; then
      echo "La rama $RAMA no está en GitHub: pushearla antes (la VM la clona de ahí)." >&2; exit 1
    fi
    echo "== Creando $NOMBRE ($TIPO, $ZONA, rama $RAMA)"
    gc compute instances create "$NOMBRE" \
      --zone="$ZONA" --machine-type="$TIPO" --provisioning-model=STANDARD \
      --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
      --boot-disk-size="${DISCO_GB}GB" --boot-disk-type=pd-ssd \
      --service-account="$CUENTA_VM" --scopes=cloud-platform \
      --labels=proposito=dmeyf \
      --metadata="repo=$REPO,rama=$RAMA" \
      --metadata-from-file=startup-script="$AQUI/vm_inicio.sh"

    echo "== Esperando la instalación (hasta $((ESPERA_MAX_S / 60)) min)"
    INICIO=$SECONDS
    until ssh_vm "$NOMBRE" "test -f /srv/listo" 2>/dev/null; do
      if (( SECONDS - INICIO > ESPERA_MAX_S )); then
        echo "No terminó. Últimas líneas del arranque:" >&2
        ssh_vm "$NOMBRE" "sudo journalctl -u google-startup-scripts --no-pager | tail -30" >&2 || true
        exit 1
      fi
      sleep 20
    done
    echo "   instalada en $(( SECONDS - INICIO )) s"

    echo "== Pruebas en la VM"
    ssh_vm "$NOMBRE" "cd /srv/dmeyf-pipeline && .venv/bin/python -V && docker --version \
      && .venv/bin/python -m pipeline_competencia02.config \
      && .venv/bin/python -m unittest discover -s pruebas -t ."
    echo "== $NOMBRE lista. Entrar: bash scripts/vm.sh entrar $NOMBRE  ·  Borrar al terminar: bash scripts/vm.sh borrar $NOMBRE"
    ;;
  entrar)
    [ $# -ge 1 ] || uso
    NOMBRE="$1"; shift
    if [ $# -gt 0 ]; then ssh_vm "$NOMBRE" "cd /srv/dmeyf-pipeline && $*"
    else gc compute ssh "$NOMBRE" --zone="$ZONA" --tunnel-through-iap; fi
    ;;
  borrar)
    [ $# -ge 1 ] || uso
    gc compute instances delete "$1" --zone="$ZONA" --delete-disks=all
    ;;
  lista)
    gc compute instances list --filter="labels.proposito=dmeyf" \
      --format="table(name,zone.basename(),machineType.basename(),status,creationTimestamp)"
    ;;
  *) uso ;;
esac
