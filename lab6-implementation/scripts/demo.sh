#!/usr/bin/env bash
# Демо-сценарий лаб. 6: 10 операций DESIGN.md подряд.
# Требуется запущенный сервер и jq:
#   uvicorn app.main:app --port 8099
#   BASE=http://127.0.0.1:8099 scripts/demo.sh
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8099}"
JQ="${JQ:-jq}"
TMP="${TMPDIR:-/tmp}/fms-demo"
mkdir -p "$TMP"
CONFLICT="$TMP/conflict.json"

TODAY=$(date +%F)
ISSUE_DATE=$(date -d '-100 days' +%F)

CITIZEN_A=$(curl -sf "$BASE/catalog/citizens" | "$JQ" -r '.[0].id')
CITIZEN_B=$(curl -sf "$BASE/catalog/citizens" | "$JQ" -r '.[1].id')
EMPLOYER=$(curl -sf "$BASE/catalog/employers" | "$JQ" -r '.[0].id')

echo "== 1/10 Регистрация патента, операция 1 «зарегистрироватьПатент»"
PATENT=$(curl -sf -X POST "$BASE/patents" \
  -H 'Content-Type: application/json' \
  -d "{\"citizen_id\":\"$CITIZEN_A\",\"series\":\"72 26\",\"number\":\"000777\",
       \"issue_date\":\"$ISSUE_DATE\",\"region_code\":\"72\",
       \"activity_codes\":[\"driver\"],\"issuing_authority\":\"УВМ УМВД России по Тюменской области\",
       \"scan\":{\"filename\":\"patent-000777.pdf\"}}")
PATENT_ID=$(echo "$PATENT" | "$JQ" -r '.patent.id')
echo "$PATENT" | "$JQ" '{id: .patent.id, status: .patent.status,
  employment_deadline: .patent.employment_deadline,
  points: [.deadline_points[].kind], next_steps: [.next_steps[].code]}'

echo "== 2/10 Сведения о патенте, операция 3 «получитьСведенияОпатенте»"
curl -sf "$BASE/patents/$PATENT_ID" | "$JQ" \
  '{number: .patent.number, citizen: .citizen.full_name,
    employment_deadline, days_left_for_employment, employment_overdue,
    has_active_contract, points: .deadline_summary.counts}'

echo "== 3/10 Настройка напоминаний, операция 8 «настроитьНапоминания»"
curl -sf -X PUT "$BASE/reminder-settings" \
  -H 'Content-Type: application/json' \
  -d "{\"citizen_id\":\"$CITIZEN_A\",\"channels\":[\"email\",\"sms\"],
       \"days\":[30,14,7,1],\"consent\":true}" \
  | "$JQ" '{settings, reminders_count, skipped_closed_points}'

echo "== 4/10 Пересчёт сроков, операция 9 «пересчитатьСрокиПатента»"
curl -sf -X POST "$BASE/patents/$PATENT_ID/recalculate" \
  -H 'Content-Type: application/json' \
  -d "{\"reason\":\"ежедневный контроль сроков\"}" \
  | "$JQ" '{reason, employment_deadline: .summary.employment_deadline,
            counts: .summary.counts, overdue: [.summary.overdue[].kind]}'

CONCLUDE_POINT=$(curl -sf "$BASE/patents/$PATENT_ID/deadline-points" \
  | "$JQ" -r '.points[] | select(.kind=="conclude_contract") | .id')

echo "== 5/10 Фиксация нарушения срока, операция 10 «зафиксироватьНарушениеСрока»"
curl -sf -X POST "$BASE/deadline-points/$CONCLUDE_POINT/violation" \
  -H 'Content-Type: application/json' \
  -d "{\"detected_at\":\"$TODAY\"}" \
  | "$JQ" '{point: .deadline_point.status, critical: .deadline_point.critical,
            violation_date: .deadline_point.violation_date,
            escalation: .escalation_reminder.escalation}'

echo "== 6/10 Заключение договора, операция 4 «заключитьДоговор»"
CONTRACT=$(curl -sf -X POST "$BASE/contracts" \
  -H 'Content-Type: application/json' \
  -d "{\"patent_id\":\"$PATENT_ID\",\"employer_id\":\"$EMPLOYER\",\"activity_code\":\"driver\",
       \"conclusion_date\":\"$TODAY\",\"kind\":\"employment\",\"position\":\"Водитель автомобиля\",
       \"document\":{\"filename\":\"dogovor-77.pdf\"}}")
CONTRACT_ID=$(echo "$CONTRACT" | "$JQ" -r '.contract.id')
echo "$CONTRACT" | "$JQ" '{id: .contract.id, status: .contract.status,
  overdue, point: .deadline_point.status, notification_task}'

echo "== 7/10 Уведомление МВД через ЕПГУ, операция 6 «направитьУведомлениеМВД»"
NOTIFICATION=$(curl -sf -X POST "$BASE/notifications" \
  -H 'Content-Type: application/json' \
  -d "{\"contract_id\":\"$CONTRACT_ID\",\"channel\":\"epgu\",
       \"confirmation\":{\"signature\":\"SIGNATURE-DEMO\"},\"allow_overdue\":true}")
NOTIFICATION_ID=$(echo "$NOTIFICATION" | "$JQ" -r '.notification.id')
echo "$NOTIFICATION" | "$JQ" '{status: .notification.status, late: .late,
  receipt: .notification.receipt_number, mvd_office: .notification.mvd_office_code,
  point: .deadline_point.status, contract_status: .contract.status}'

echo "   Проверка ИНВ-7: повторное уведомление по тому же договору запрещено"
curl -s -o "$CONFLICT" -w '   HTTP %{http_code}\n' \
  -X POST "$BASE/notifications" -H 'Content-Type: application/json' \
  -d "{\"contract_id\":\"$CONTRACT_ID\",\"channel\":\"post\",\"confirmation\":{\"inventory\":\"опись\"}}"
"$JQ" '{code, message}' "$CONFLICT"

echo "== 8/10 Возврат уведомления, операция 7 «зафиксироватьВозвратУведомления»"
curl -sf -X POST "$BASE/notifications/$NOTIFICATION_ID/return" \
  -H 'Content-Type: application/json' \
  -d "{\"reason\":\"адресат не найден\",\"document\":{\"filename\":\"vozvrat.pdf\"}}" \
  | "$JQ" '{status: .notification.status, attempts: .notification.attempts,
            task_state, point: .deadline_point.status}'

echo "== 9/10 Отмена договора, операция 5 «отменитьДоговор»"
SECOND=$(curl -sf -X POST "$BASE/patents" \
  -H 'Content-Type: application/json' \
  -d "{\"citizen_id\":\"$CITIZEN_B\",\"series\":\"72 26\",\"number\":\"000778\",
       \"issue_date\":\"$TODAY\",\"region_code\":\"72\",
       \"activity_codes\":[\"builder\"],\"issuing_authority\":\"УВМ УМВД России по Тюменской области\"}")
SECOND_ID=$(echo "$SECOND" | "$JQ" -r '.patent.id')
DRAFT=$(curl -sf -X POST "$BASE/contracts" \
  -H 'Content-Type: application/json' \
  -d "{\"patent_id\":\"$SECOND_ID\",\"employer_id\":\"$EMPLOYER\",\"activity_code\":\"builder\",
       \"conclusion_date\":\"$TODAY\",\"kind\":\"employment\",\"position\":\"Строитель\",
       \"consent_confirmed\":false}")
DRAFT_ID=$(echo "$DRAFT" | "$JQ" -r '.contract.id')
curl -sf -X POST "$BASE/contracts/$DRAFT_ID/cancel" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"стороны не подтвердили согласие"}' \
  | "$JQ" '{id: .contract.id, status: .contract.status, reason: .contract.cancel_reason,
            history_preserved, deadline_point_state}'

echo "== 10/10 Архивирование патента, операция 2 «пометитьПатентАрхивным»"
curl -sf -X POST "$BASE/patents/$SECOND_ID/archive" \
  -H 'Content-Type: application/json' \
  -d '{"basis":"mvd_decision","reason":"решение МВД об аннулировании"}' \
  | "$JQ" '{status: .patent.status, archive_basis: .patent.archive_basis,
            cancelled_deadline_points, cancelled_reminders}'

echo "== Проверка ИНВ-1: архив патента с действующим договором запрещён"
curl -s -o "$CONFLICT" -w 'HTTP %{http_code}\n' \
  -X POST "$BASE/patents/$PATENT_ID/archive" -H 'Content-Type: application/json' \
  -d '{"basis":"annulled","reason":"попытка архивации"}'
"$JQ" '{code, message}' "$CONFLICT"
