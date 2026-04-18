#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STAMP="${1:-$(date -u +%Y-%m-%d)}"
REPORTS_DIR="analysis_reports"
mkdir -p "$REPORTS_DIR"

SCAN_ARQUIVOS="$REPORTS_DIR/SCAN_ARQUIVOS_${STAMP}.txt"
SCAN_CODIGOS_LISTA="$REPORTS_DIR/SCAN_CODIGOS_LISTA_${STAMP}.txt"
SCAN_CODIGO_COMPLETO="$REPORTS_DIR/SCAN_CODIGO_COMPLETO_${STAMP}.txt"
LOG_FILE="$REPORTS_DIR/EXECUCAO_MODO_COMPUTADOR_SCAN_CODIGOS_${STAMP}.log"
SUMMARY_FILE="$REPORTS_DIR/EXECUCAO_MODO_COMPUTADOR_SCAN_CODIGOS_${STAMP}.md"

printf '/run rg --files > %s\n/run find core modules protocols -type f > %s\n/run cat core/atena_terminal_assistant.py modules/computer_actuator.py protocols/atena_invoke.py > %s\n/exit\n' \
  "$SCAN_ARQUIVOS" "$SCAN_CODIGOS_LISTA" "$SCAN_CODIGO_COMPLETO" \
  | ./atena assistant | tee "$LOG_FILE"

{
  echo "# Execução modo computador — varredura de códigos (${STAMP})"
  echo
  echo "## Artefatos gerados"
  echo "- \`${SCAN_ARQUIVOS}\`"
  echo "- \`${SCAN_CODIGOS_LISTA}\`"
  echo "- \`${SCAN_CODIGO_COMPLETO}\`"
  echo "- \`${LOG_FILE}\`"
  echo
  echo "## Prévia"
  echo "- Total de arquivos listados: $(wc -l < "$SCAN_ARQUIVOS" | tr -d ' ')"
  echo "- Total de códigos (core/modules/protocols): $(wc -l < "$SCAN_CODIGOS_LISTA" | tr -d ' ')"
  echo
  echo "## Status"
  echo "Varredura concluída no modo computador com extração de inventário e dump consolidado."
} > "$SUMMARY_FILE"

echo "✅ Relatório salvo em: $SUMMARY_FILE"
