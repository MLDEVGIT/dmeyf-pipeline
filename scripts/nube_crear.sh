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

echo "== Estado"
gc sql instances describe "$INSTANCIA" --format="yaml(
  state, databaseVersion, region, settings.tier,
  settings.backupConfiguration.enabled, settings.backupConfiguration.pointInTimeRecoveryEnabled,
  settings.deletionProtectionEnabled, settings.maintenanceWindow, settings.denyMaintenancePeriods,
  settings.connectorEnforcement, settings.ipConfiguration.sslMode)"
