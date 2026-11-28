#!/usr/bin/env bash
# Crea (o deja como corresponde) la base del registro: una instancia de Cloud SQL para PostgreSQL.
# Idempotente: si la instancia ya existe, vuelve a aplicar los ajustes y no falla.
#
#   bash scripts/nube_crear.sh
#
# Lo que deja explícito (diseño, decisión 5): copias automáticas diarias, recuperación a un punto en el
# tiempo, protección contra borrado y un período sin mantenimiento que cubre la clase del 10-dic.
# Sin redes autorizadas: solo se entra con el conector de Cloud SQL, con identidad de Google.
set -euo pipefail

PROYECTO="${DMEYF_PROYECTO:-proj-uba-261012163242176}"
REGION="${DMEYF_REGION:-northamerica-northeast2}"
INSTANCIA="${DMEYF_INSTANCIA:-dmeyf-registro}"
VERSION_PG="POSTGRES_17"          # la misma versión mayor que docker-compose.yml (pruebas locales)
TIPO="db-f1-micro"                # núcleo compartido: el registro escribe pocas filas por corrida
DISCO_GB=10

# Mantenimiento: ventana semanal fuera del horario de clase (domingo 7 UTC = 4 de Argentina) y un período
# sin mantenimiento del 1 al 20 de diciembre, que cubre el ensayo general, la clase y el video.
VENTANA_DIA="SUN"
VENTANA_HORA=7
SIN_MANTENIMIENTO_DESDE="2026-12-01"
SIN_MANTENIMIENTO_HASTA="2026-12-20"
SIN_MANTENIMIENTO_HORA="00:00:00"

gc() { gcloud --project="$PROYECTO" --quiet "$@"; }

echo "== API de Cloud SQL"
gc services enable sqladmin.googleapis.com

AJUSTES=(
  --tier="$TIPO"
  --edition=ENTERPRISE
  --backup-start-time=06:00
  --retained-backups-count=7
  --enable-point-in-time-recovery
  --retained-transaction-log-days=7
  --deletion-protection
  --maintenance-window-day="$VENTANA_DIA"
  --maintenance-window-hour="$VENTANA_HORA"
  --deny-maintenance-period-start-date="$SIN_MANTENIMIENTO_DESDE"
  --deny-maintenance-period-end-date="$SIN_MANTENIMIENTO_HASTA"
  --deny-maintenance-period-time="$SIN_MANTENIMIENTO_HORA"
  --database-flags=cloudsql.iam_authentication=on
  --connector-enforcement=REQUIRED
  --ssl-mode=ENCRYPTED_ONLY
)

if gc sql instances describe "$INSTANCIA" --format="value(name)" >/dev/null 2>&1; then
  echo "== La instancia $INSTANCIA ya existe: se vuelven a aplicar los ajustes"
  gc sql instances patch "$INSTANCIA" "${AJUSTES[@]}"
else
  echo "== Creando $INSTANCIA ($VERSION_PG, $TIPO, $REGION)"
  gc sql instances create "$INSTANCIA" \
    --database-version="$VERSION_PG" \
    --region="$REGION" \
    --availability-type=zonal \
    --storage-type=SSD \
    --storage-size="${DISCO_GB}GB" \
    --storage-auto-increase \
    "${AJUSTES[@]}"
fi

echo "== Base dmeyf"
if ! gc sql databases describe dmeyf --instance="$INSTANCIA" >/dev/null 2>&1; then
  gc sql databases create dmeyf --instance="$INSTANCIA"
fi

echo "== Cuenta de servicio de las VMs (bucket de datos y base, nada más)"
# Las VMs no corren con la cuenta por defecto del proyecto (que es editora de todo): con esta, una VM lee y
# escribe el bucket y se conecta a la base con su identidad, pero no puede crear ni borrar recursos.
BUCKET="${DMEYF_BUCKET:-gs://agustinarazanov_buckito2026}"
CUENTA_VM="dmeyf-vm@${PROYECTO}.iam.gserviceaccount.com"
gc services enable compute.googleapis.com iap.googleapis.com
if ! gc iam service-accounts describe "$CUENTA_VM" >/dev/null 2>&1; then
  gc iam service-accounts create dmeyf-vm --display-name="VMs de trabajo de dmeyf-pipeline"
fi
# Una cuenta recién creada tarda unos segundos en existir para IAM: cada permiso se reintenta.
reintentar() { for i in 1 2 3 4 5 6; do "$@" >/dev/null && return 0; sleep 10; done; "$@"; }
for ROL in roles/cloudsql.client roles/cloudsql.instanceUser roles/logging.logWriter; do
  reintentar gc projects add-iam-policy-binding "$PROYECTO" --member="serviceAccount:$CUENTA_VM" --role="$ROL" \
    --condition=None
done
gc storage buckets add-iam-policy-binding "$BUCKET" --member="serviceAccount:$CUENTA_VM" \
  --role=roles/storage.objectAdmin >/dev/null
# Usuario de base de la cuenta (Cloud SQL lo nombra sin «.gserviceaccount.com»); sus permisos sobre los esquemas
# los da la tarea de roles de la base (operador, lector, tablero).
USUARIO_VM="${CUENTA_VM%.gserviceaccount.com}"
if ! gc sql users list --instance="$INSTANCIA" --format="value(name)" | grep -qx "$USUARIO_VM"; then
  gc sql users create "$USUARIO_VM" --instance="$INSTANCIA" --type=cloud_iam_service_account
fi

echo "== Estado"
gc sql instances describe "$INSTANCIA" --format="yaml(
  state, databaseVersion, region, settings.tier,
  settings.backupConfiguration.enabled, settings.backupConfiguration.pointInTimeRecoveryEnabled,
  settings.deletionProtectionEnabled, settings.maintenanceWindow, settings.denyMaintenancePeriods,
  settings.connectorEnforcement, settings.ipConfiguration.sslMode)"
