#!/usr/bin/env bash
# Демо-сценарий лаб. 6: 7 вызовов подряд по основным операциям.
# Требуется запущенный сервер и jq:
#   uvicorn app.main:app --port 8099
#   BASE=http://127.0.0.1:8099 scripts/demo.sh
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8099}"
JQ="${JQ:-jq}"
TMP="${TMPDIR:-/tmp}/fms-demo"
mkdir -p "$TMP"
OUT="${OUT:-$TMP/report.csv}"
HEADERS="$TMP/headers.txt"
CONFLICT="$TMP/conflict.json"

CITIZEN=$(curl -sf "$BASE/users" | "$JQ" -r '.[] | select(.login=="ig-petrov") | .citizen_id')
EMPLOYER=$(curl -sf "$BASE/users" | "$JQ" -r '.[] | select(.login=="hr-romashka") | .employer_id')

echo "== 1/7 Регистрация патента (операция 1)"
PATENT=$(curl -sf -X POST "$BASE/patents" \
  -H 'Content-Type: application/json' \
  -d "{\"citizen_id\":\"$CITIZEN\",\"series\":\"72 26\",\"number\":\"000777\",
       \"issue_date\":\"2026-10-01\",\"region_code\":\"72\",
       \"activity_codes\":[\"driver\"],\"issuing_authority\":\"УВМ УМВД России по Тюменской области\",
       \"scan\":{\"filename\":\"patent-000777.pdf\"}}")
PATENT_ID=$(echo "$PATENT" | "$JQ" -r '.patent.id')
echo "$PATENT" | "$JQ" '{id: .patent.id, status: .patent.status,
  employment_deadline: .patent.employment_deadline,
  points: [.deadline_points[].kind], next_steps: [.next_steps[].code]}'

echo "== 2/7 Заключение трудового договора (операция 4)"
CONTRACT=$(curl -sf -X POST "$BASE/contracts" \
  -H 'Content-Type: application/json' \
  -d "{\"patent_id\":\"$PATENT_ID\",\"employer_id\":\"$EMPLOYER\",\"activity_code\":\"driver\",
       \"conclusion_date\":\"2026-10-05\",\"kind\":\"employment\",\"position\":\"Водитель автомобиля\",
       \"document\":{\"filename\":\"dogovor-77.pdf\"}}")
CONTRACT_ID=$(echo "$CONTRACT" | "$JQ" -r '.contract.id')
echo "$CONTRACT" | "$JQ" '{id: .contract.id, status: .contract.status, overdue,
  point: .deadline_point.status, notification_task}'

echo "== 3/7 Уведомление МВД через ЕПГУ (операция 6)"
NOTIFICATION=$(curl -sf -X POST "$BASE/notifications" \
  -H 'Content-Type: application/json' \
  -d "{\"contract_id\":\"$CONTRACT_ID\",\"channel\":\"epgu\",
       \"confirmation\":{\"signature\":\"SIGNATURE-DEMO\"}}")
echo "$NOTIFICATION" | "$JQ" '{status: .notification.status, receipt: .notification.receipt_number,
  mvd_office: .notification.mvd_office_code, point: .deadline_point.status,
  contract_status: .contract.status, evidence: .evidence.documents}'

echo "== 4/7 Авансовый платёж НДФЛ за 2026-10 (операция 11)"
PAYMENT=$(curl -sf -X POST "$BASE/payments" \
  -H 'Content-Type: application/json' \
  -d "{\"patent_id\":\"$PATENT_ID\",\"period\":\"2026-10\",\"amount\":\"6000.00\",
       \"payment_date\":\"2026-10-25\",\"document_number\":\"PP-2026-10\",
       \"document\":{\"filename\":\"platezhka-10.pdf\"}}")
echo "$PAYMENT" | "$JQ" '{payment: .payment.status, amount: .payment.amount,
  paid_until: .patent.paid_until, patent_status: .patent.status, point: .deadline_point.status}'

echo "== 5/7 Настройка напоминаний (операция 8)"
REMINDERS=$(curl -sf -X PUT "$BASE/reminder-settings" \
  -H 'Content-Type: application/json' -H 'X-User-Login: ig-petrov' \
  -d '{"channels":["email","sms"],"days":[30,14,7,3,1],"consent":true}')
echo "$REMINDERS" | "$JQ" '{profile_id, settings, reminders_count, skipped_closed_points}'

echo "== 6/7 Формирование реестра (операция 15)"
REPORT=$(curl -sf "$BASE/reports" -H 'X-User-Login: admin')
REPORT_ID=$(echo "$REPORT" | "$JQ" -r '.id')
echo "$REPORT" | "$JQ" '{id, snapshot_at, row_count, critical_count, rows}'

echo "== 7/7 Выгрузка реестра в CSV (операция 16)"
curl -sf -D "$HEADERS" "$BASE/reports/$REPORT_ID/export?format=csv" -o "$OUT"
grep -Ei '^(content-type|content-disposition|x-export-hash|x-export-anonymized)' "$HEADERS"
head -n 2 "$OUT"

echo "== Проверка инварианта ИНВ-8: повторное уведомление запрещено"
curl -s -o "$CONFLICT" -w 'HTTP %{http_code}\n' \
  -X POST "$BASE/notifications" -H 'Content-Type: application/json' \
  -d "{\"contract_id\":\"$CONTRACT_ID\",\"channel\":\"post\",\"confirmation\":{\"inventory\":\"опись\"}}"
"$JQ" '{code, message}' "$CONFLICT"
