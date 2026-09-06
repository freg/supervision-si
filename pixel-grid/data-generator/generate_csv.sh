#!/usr/bin/env bash
# Génère le CSV brut à partir d'un fichier de configuration JSON —
# backend-agnostique (ni SQLite ni PostgreSQL ici), voir load_sqlite.sh
# et load_postgres.sh pour le chargement en base.
#
# Usage : ./generate_csv.sh configs/etat_example.json /tmp/etat.csv
#
# Dépendances : jq, awk (POSIX standard suffit), date GNU (option -d).

set -euo pipefail

CONFIG_FILE="${1:?Usage: $0 <config.json> <output.csv>}"
CSV_FILE="${2:?Usage: $0 <config.json> <output.csv>}"

for cmd in jq awk; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Dépendance manquante : $cmd" >&2; exit 1; }
done

NOM=$(jq -r '.nom' "$CONFIG_FILE")
TYPE=$(jq -r '.type' "$CONFIG_FILE")
KIND=$(jq -r '.kind' "$CONFIG_FILE")
START_ISO=$(jq -r '.start' "$CONFIG_FILE")
END_ISO=$(jq -r '.end' "$CONFIG_FILE")
INTERVAL_MIN=$(jq -r '.interval_minutes' "$CONFIG_FILE")

START_EPOCH=$(date -u -d "$START_ISO" +%s)
END_EPOCH=$(date -u -d "$END_ISO" +%s)
STEP_SECONDS=$((INTERVAL_MIN * 60))

TOTAL_POINTS=$(( (END_EPOCH - START_EPOCH) / STEP_SECONDS + 1 ))
echo "Génération de ${TOTAL_POINTS} points pour '${NOM}' (type=${TYPE}, kind=${KIND})..." >&2

SERVICES=$(jq -r '.data_fields.service | join(",")' "$CONFIG_FILE")
OSES=$(jq -r '.data_fields.os | join(",")' "$CONFIG_FILE")

WINDOWS_FILE=$(mktemp)
trap 'rm -f "$WINDOWS_FILE"' EXIT

if [ "$KIND" = "integer_enum" ]; then
  jq -r '.incident_windows[]? | [(.start), (.end), (.probabilities."-1"), (.probabilities."0"), (.probabilities."1")] | @tsv' "$CONFIG_FILE" \
  | while IFS=$'\t' read -r wstart wend p_neg1 p_0 p_1; do
      ws=$(date -u -d "$wstart" +%s); we=$(date -u -d "$wend" +%s)
      printf "%s\t%s\t%s\t%s\t%s\n" "$ws" "$we" "$p_neg1" "$p_0" "$p_1" >> "$WINDOWS_FILE"
    done

  P_NEG1=$(jq -r '.probabilities."-1"' "$CONFIG_FILE")
  P_0=$(jq -r '.probabilities."0"' "$CONFIG_FILE")
  P_1=$(jq -r '.probabilities."1"' "$CONFIG_FILE")

  awk -v start="$START_EPOCH" -v end="$END_EPOCH" -v step="$STEP_SECONDS" \
      -v nom="$NOM" -v type="$TYPE" \
      -v p_neg1="$P_NEG1" -v p_0="$P_0" -v p_1="$P_1" \
      -v services="$SERVICES" -v oses="$OSES" \
      -v windows_file="$WINDOWS_FILE" -v seed="$RANDOM" '
    function csv_escape(s) { gsub(/"/, "\"\"", s); return "\"" s "\""; }
    BEGIN {
      srand(seed);
      split(services, svc_arr, ",");
      split(oses, os_arr, ",");
      n_svc = length(svc_arr); n_os = length(os_arr);

      n_windows = 0;
      while ((getline line < windows_file) > 0) {
        n_windows++;
        split(line, f, "\t");
        w_start[n_windows] = f[1]; w_end[n_windows] = f[2];
        w_p_neg1[n_windows] = f[3]; w_p_0[n_windows] = f[4]; w_p_1[n_windows] = f[5];
      }
      close(windows_file);

      for (t = start; t <= end; t += step) {
        cur_neg1 = p_neg1; cur_0 = p_0; cur_1 = p_1;
        for (i = 1; i <= n_windows; i++) {
          if (t >= w_start[i] && t <= w_end[i]) {
            cur_neg1 = w_p_neg1[i]; cur_0 = w_p_0[i]; cur_1 = w_p_1[i];
          }
        }

        r = rand();
        if (r < cur_neg1) valeur = -1;
        else if (r < cur_neg1 + cur_0) valeur = 0;
        else valeur = 1;

        svc = svc_arr[int(rand() * n_svc) + 1];
        osv = os_arr[int(rand() * n_os) + 1];
        data_json = "{\"service\":\"" svc "\",\"os\":\"" osv "\"}";

        printf "%d,%d,%s,%s,%s\n", t, valeur, csv_escape(nom), csv_escape(type), csv_escape(data_json);
      }
    }
  ' > "$CSV_FILE"

elif [ "$KIND" = "continuous" ]; then
  jq -r '.incident_windows[]? | [(.start), (.end), (.base_value), (.noise_amplitude)] | @tsv' "$CONFIG_FILE" \
  | while IFS=$'\t' read -r wstart wend base noise; do
      ws=$(date -u -d "$wstart" +%s); we=$(date -u -d "$wend" +%s)
      printf "%s\t%s\t%s\t%s\n" "$ws" "$we" "$base" "$noise" >> "$WINDOWS_FILE"
    done

  MAX_VALUE=$(jq -r '.max_value' "$CONFIG_FILE")
  BASE_VALUE=$(jq -r '.base_value' "$CONFIG_FILE")
  NOISE_AMP=$(jq -r '.noise_amplitude' "$CONFIG_FILE")
  DAILY_AMP=$(jq -r '.daily_cycle_amplitude' "$CONFIG_FILE")

  awk -v start="$START_EPOCH" -v end="$END_EPOCH" -v step="$STEP_SECONDS" \
      -v nom="$NOM" -v type="$TYPE" \
      -v max_value="$MAX_VALUE" -v base_value="$BASE_VALUE" \
      -v noise_amplitude="$NOISE_AMP" -v daily_amp="$DAILY_AMP" \
      -v services="$SERVICES" -v oses="$OSES" \
      -v windows_file="$WINDOWS_FILE" -v seed="$RANDOM" '
    function csv_escape(s) { gsub(/"/, "\"\"", s); return "\"" s "\""; }
    BEGIN {
      srand(seed);
      PI = 3.14159265358979;
      split(services, svc_arr, ",");
      split(oses, os_arr, ",");
      n_svc = length(svc_arr); n_os = length(os_arr);

      n_windows = 0;
      while ((getline line < windows_file) > 0) {
        n_windows++;
        split(line, f, "\t");
        w_start[n_windows] = f[1]; w_end[n_windows] = f[2];
        w_base[n_windows] = f[3]; w_noise[n_windows] = f[4];
      }
      close(windows_file);

      for (t = start; t <= end; t += step) {
        cur_base = base_value; cur_noise = noise_amplitude;
        for (i = 1; i <= n_windows; i++) {
          if (t >= w_start[i] && t <= w_end[i]) {
            cur_base = w_base[i]; cur_noise = w_noise[i];
          }
        }

        hour_of_day = (t % 86400) / 3600.0;
        cycle = daily_amp * sin(2 * PI * hour_of_day / 24.0);
        noise = (rand() - 0.5) * 2 * cur_noise;
        valeur = cur_base + cycle + noise;
        if (valeur < 0) valeur = 0;
        if (valeur > max_value) valeur = max_value;

        svc = svc_arr[int(rand() * n_svc) + 1];
        osv = os_arr[int(rand() * n_os) + 1];
        data_json = "{\"service\":\"" svc "\",\"os\":\"" osv "\"}";

        printf "%d,%.2f,%s,%s,%s\n", t, valeur, csv_escape(nom), csv_escape(type), csv_escape(data_json);
      }
    }
  ' > "$CSV_FILE"

else
  echo "kind inconnu dans la config : '$KIND' (attendu: integer_enum ou continuous)" >&2
  exit 1
fi

LINE_COUNT=$(wc -l < "$CSV_FILE")
echo "CSV généré : ${CSV_FILE} (${LINE_COUNT} lignes)" >&2
