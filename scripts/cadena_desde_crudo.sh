#!/usr/bin/env bash
# Todo desde el crudo del curso, en orden y sin archivos previos: historia de 2019, target, features, la fábrica
# de un catálogo (subido al bucket), los archivos mensuales del ensayo y la secuencia con ese catálogo fabricado.
# Pensado para la VM; cada paso deja su hora en el log.
#
#   bash scripts/vm.sh entrar <vm> "nohup bash scripts/cadena_desde_crudo.sh tc01 > /srv/cadena_tc01.log 2>&1 &"
#
# Argumentos: catálogo (tc01), primer y último mes de la secuencia (202001 202006).
set -euo pipefail
cd "$(dirname "$0")/.."
CATALOGO="${1:-tc01}"
DESDE="${2:-202001}"
HASTA="${3:-202006}"
PY=.venv/bin/python
MODELOS="$($PY -c 'from pipeline_competencia02.config import RUTAS; print(RUTAS.modelos)')"
paso() { echo "== $(date -u +%FT%TZ) $*"; }

paso "historia de 2019 desde el crudo";  $PY entrenamiento/legado/02_convertir_parquet.py
paso "target versión 1";                 $PY entrenamiento/legado/03_construir_target.py
paso "features de 2019";                 $PY entrenamiento/legado/04_generar_features.py
paso "target versión 2";                 $PY -m experimentos.tc01_target_2019
paso "fábrica de $CATALOGO";             $PY -m entrenamiento.fabrica --catalogo "$CATALOGO" --hilos "$(nproc)" --subir
paso "archivos mensuales $DESDE–$HASTA"; $PY -m pipeline_competencia02.preparar_insumos --desde "$DESDE" --hasta "$HASTA"
paso "secuencia $DESDE–$HASTA con el $CATALOGO fabricado"
$PY -m pipeline_competencia02.correr_meses --nueva "secuencia_${CATALOGO}_fabricado" --desde "$DESDE" --hasta "$HASTA" \
  --reintento-en "$(( DESDE + 2 ))" --catalogo "$MODELOS/estrategias_${CATALOGO}.json" \
  --resumen "/srv/secuencia_${CATALOGO}_fabricado_${DESDE}_${HASTA}.json"
paso "fin"
