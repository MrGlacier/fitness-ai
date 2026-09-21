#!/usr/bin/env bash

set -Eeuo pipefail

# Steuert ausschließlich die zu Fitness AI gehörenden Komponenten:
# llama-server und API in tmux, Open WebUI sowie das Compose-Dashboard.

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

#MODEL="/home/MrGlacier/.cache/llama.cpp/Qwen_Qwen3-14B-GGUF_Qwen3-14B-Q4_K_M.gguf"
MODEL="unsloth/Qwen3.6-35B-A3B-GGUF:UD-IQ4_NL"

TMUX_SESSION="fitness-ai"
OPEN_WEBUI_CONTAINER="open-webui"
DASHBOARD_CONTAINER="fitness-ai-dashboard"

LLM_URL="http://127.0.0.1:8080/health"
API_URL="http://127.0.0.1:8000/"
WEBUI_URL="http://127.0.0.1:3000/"
DASHBOARD_HEALTH_URL="http://127.0.0.1:8081/health"
DASHBOARD_URL="http://127.0.0.1:8081/"

info() { echo "[INFO] $1"; }
ok() { echo "[ OK ] $1"; }
error() { echo "[ERROR] $1" >&2; }

tmux_exists() {
    tmux has-session -t "$TMUX_SESSION" 2>/dev/null
}

http_reachable() {
    curl -fsS --max-time 2 --output /dev/null "$1" 2>/dev/null
}

wait_for_http() {
    local label="$1"
    local url="$2"
    local attempts="${3:-30}"
    local attempt

    for ((attempt = 1; attempt <= attempts; attempt++)); do
        if http_reachable "$url"; then
            ok "$label ist erreichbar."
            return 0
        fi
        sleep 1
    done

    error "$label ist nach ${attempts} Sekunden nicht erreichbar: $url"
    return 1
}

wait_for_shutdown() {
    local label="$1"
    local url="$2"
    local attempts="${3:-10}"
    local attempt

    for ((attempt = 1; attempt <= attempts; attempt++)); do
        if ! http_reachable "$url"; then
            ok "$label ist gestoppt."
            return 0
        fi
        sleep 1
    done

    error "$label antwortet weiterhin: $url"
    return 1
}

detect_docker_command() {
    if ! command -v docker >/dev/null 2>&1; then
        error "Docker wurde nicht gefunden."
        return 1
    fi

    if docker info >/dev/null 2>&1; then
        DOCKER=(docker)
    elif command -v sudo >/dev/null 2>&1 && sudo -n docker info >/dev/null 2>&1; then
        DOCKER=(sudo docker)
    else
        error "Kein Zugriff auf den Docker-Daemon."
        return 1
    fi

    if ! "${DOCKER[@]}" compose version >/dev/null 2>&1; then
        error "Docker Compose ist nicht verfügbar."
        return 1
    fi
}

compose() {
    "${DOCKER[@]}" compose \
        --project-directory "$PROJECT_DIR" \
        -f "$COMPOSE_FILE" \
        "$@"
}

container_exists() {
    "${DOCKER[@]}" inspect "$1" >/dev/null 2>&1
}

container_running() {
    [[ "$("${DOCKER[@]}" inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" == "true" ]]
}

start_open_webui() {
    info "Prüfe Open-WebUI-Container..."

    if container_exists "$OPEN_WEBUI_CONTAINER"; then
        if container_running "$OPEN_WEBUI_CONTAINER"; then
            ok "Open WebUI läuft bereits."
        else
            info "Starte vorhandenen Open-WebUI-Container..."
            "${DOCKER[@]}" start "$OPEN_WEBUI_CONTAINER" >/dev/null
            ok "Open WebUI gestartet."
        fi
        return
    fi

    info "Open WebUI ist noch nicht eingerichtet; erstelle den Container..."
    "${DOCKER[@]}" run -d \
        -p 3000:8080 \
        --add-host=host.docker.internal:host-gateway \
        -v open-webui:/app/backend/data \
        --name "$OPEN_WEBUI_CONTAINER" \
        --restart always \
        ghcr.io/open-webui/open-webui:main >/dev/null
    ok "Open WebUI wurde eingerichtet und gestartet."
}

start_dashboard() {
    if container_exists "$DASHBOARD_CONTAINER" \
        && container_running "$DASHBOARD_CONTAINER" \
        && http_reachable "$DASHBOARD_HEALTH_URL"; then
        ok "Dashboard läuft bereits."
        return
    fi

    info "Starte Dashboard über Docker Compose..."
    compose up -d --build dashboard
    ok "Dashboard-Container wurde gestartet."
}

stop_dashboard() {
    if ! container_exists "$DASHBOARD_CONTAINER"; then
        info "Dashboard-Container existiert nicht."
    elif container_running "$DASHBOARD_CONTAINER"; then
        info "Stoppe Dashboard über Docker Compose..."
        compose stop dashboard
        ok "Dashboard gestoppt."
    else
        info "Dashboard läuft nicht."
    fi
}

stop_container() {
    local label="$1"
    local container="$2"

    if ! container_exists "$container"; then
        info "$label-Container existiert nicht."
    elif container_running "$container"; then
        info "Stoppe $label..."
        "${DOCKER[@]}" stop "$container" >/dev/null
        ok "$label gestoppt."
    else
        info "$label läuft nicht."
    fi
}

create_tmux_session() {
    info "Erstelle tmux-Session '$TMUX_SESSION'..."

    tmux new-session \
        -d -s "$TMUX_SESSION" -n "fitness-ai" -c "$PROJECT_DIR" \
        "exec llama-server \
            -hf '$MODEL' \
            --host 127.0.0.1 \
            --port 8080 \
            -c 131072 \
            -fa on \
            -ctk q8_0 \
            -ctv q8_0 \
            --n-gpu-layers 99 \
            --n-cpu-moe 31 \
            --jinja \
            --no-reasoning-preserve \
            --temp 0.6 \
            --top-p 0.95 \
            --top-k 20"

    tmux split-window \
        -v -t "$TMUX_SESSION:0" -c "$PROJECT_DIR" \
        "exec env PYTHONPATH=. uv run uvicorn api:app \
            --host 0.0.0.0 \
            --port 8000 \
            --reload"

    local docker_logs_command
    if [[ "${DOCKER[0]}" == "sudo" ]]; then
        docker_logs_command="sudo docker logs -f '$OPEN_WEBUI_CONTAINER'"
    else
        docker_logs_command="docker logs -f '$OPEN_WEBUI_CONTAINER'"
    fi

    tmux split-window \
        -v -t "$TMUX_SESSION:0" -c "$PROJECT_DIR" \
        "$docker_logs_command"

    tmux select-layout -t "$TMUX_SESSION:0" even-vertical
    tmux select-pane -t "$TMUX_SESSION:0.0" -T "LLM"
    tmux select-pane -t "$TMUX_SESSION:0.1" -T "API"
    tmux select-pane -t "$TMUX_SESSION:0.2" -T "Open WebUI"
    tmux set-option -t "$TMUX_SESSION" pane-border-status top
    tmux select-pane -t "$TMUX_SESSION:0.0"
    ok "tmux-Session '$TMUX_SESSION' erstellt."
}

start_tmux() {
    if tmux_exists; then
        if http_reachable "$LLM_URL" && http_reachable "$API_URL"; then
            ok "LLM und Fitness API laufen bereits in '$TMUX_SESSION'."
            return
        fi

        info "Die tmux-Session ist unvollständig; starte ihre Komponenten neu..."
        tmux kill-session -t "$TMUX_SESSION"
        sleep 2
    elif http_reachable "$LLM_URL" || http_reachable "$API_URL"; then
        error "LLM oder API laufen außerhalb der verwalteten tmux-Session."
        error "Fremde Prozesse werden weder übernommen noch beendet."
        return 1
    fi

    create_tmux_session
}

start_all() {
    echo
    echo "========================================"
    echo " Fitness AI starten"
    echo "========================================"
    echo

    detect_docker_command
    start_open_webui
    start_tmux
    wait_for_http "llama-server" "$LLM_URL" 90
    wait_for_http "Fitness API" "$API_URL" 45

    start_dashboard
    wait_for_http "Open WebUI" "$WEBUI_URL" 60
    wait_for_http "Dashboard-Healthcheck" "$DASHBOARD_HEALTH_URL" 45
    wait_for_http "Dashboard" "$DASHBOARD_URL" 15

    echo
    echo "========================================"
    echo " Fitness AI ist bereit"
    echo "========================================"
    echo
    echo "Open WebUI:  http://localhost:3000"
    echo "Fitness API: http://localhost:8000"
    echo "Dashboard:   http://localhost:8081"
    echo "LLM:         http://localhost:8080"
    echo "Console:     ./fitness-ai.sh console"
    echo
}

stop_all() {
    echo
    echo "========================================"
    echo " Fitness AI stoppen"
    echo "========================================"
    echo

    detect_docker_command
    stop_dashboard
    stop_container "Open WebUI" "$OPEN_WEBUI_CONTAINER"

    if tmux_exists; then
        info "Stoppe tmux-Session '$TMUX_SESSION'..."
        tmux kill-session -t "$TMUX_SESSION"
        ok "LLM und Fitness API wurden beendet."
    else
        info "tmux-Session '$TMUX_SESSION' läuft nicht."
    fi

    wait_for_shutdown "Dashboard" "$DASHBOARD_HEALTH_URL" 10
    wait_for_shutdown "Fitness API" "$API_URL" 10
    wait_for_shutdown "llama-server" "$LLM_URL" 10
    wait_for_shutdown "Open WebUI" "$WEBUI_URL" 10

    echo
    ok "Fitness AI wurde vollständig gestoppt."
    echo
}

restart_all() {
    stop_all
    info "Warte kurz auf den vollständigen Shutdown..."
    sleep 2
    start_all
}

print_http_status() {
    local label="$1"
    local url="$2"
    if http_reachable "$url"; then
        printf "%-16s %s\n" "$label:" "ERREICHBAR"
    else
        printf "%-16s %s\n" "$label:" "NICHT ERREICHBAR"
    fi
}

print_container_status() {
    local label="$1"
    local container="$2"
    if ! container_exists "$container"; then
        printf "%-16s %s\n" "$label:" "NICHT EINGERICHTET"
    elif container_running "$container"; then
        printf "%-16s %s\n" "$label:" "LÄUFT"
    else
        printf "%-16s %s\n" "$label:" "GESTOPPT"
    fi
}

show_status() {
    detect_docker_command
    echo
    echo "========================================"
    echo " Fitness AI Status"
    echo "========================================"
    echo

    if tmux_exists; then
        printf "%-16s %s\n" "tmux:" "LÄUFT"
    else
        printf "%-16s %s\n" "tmux:" "GESTOPPT"
    fi
    print_container_status "Open WebUI" "$OPEN_WEBUI_CONTAINER"
    print_container_status "Dashboard" "$DASHBOARD_CONTAINER"
    echo
    print_http_status "llama-server" "$LLM_URL"
    print_http_status "Fitness API" "$API_URL"
    print_http_status "Open WebUI" "$WEBUI_URL"
    print_http_status "Dashboard" "$DASHBOARD_HEALTH_URL"
    echo
}

show_logs() {
    detect_docker_command
    if tmux_exists; then
        echo "=== LLM ==="
        tmux capture-pane -p -t "$TMUX_SESSION:0.0" -S -80
        echo "=== Fitness API ==="
        tmux capture-pane -p -t "$TMUX_SESSION:0.1" -S -80
    else
        info "Keine tmux-Session vorhanden."
    fi

    echo "=== Open WebUI ==="
    if container_exists "$OPEN_WEBUI_CONTAINER"; then
        "${DOCKER[@]}" logs --tail 80 "$OPEN_WEBUI_CONTAINER"
    else
        info "Open-WebUI-Container existiert nicht."
    fi

    echo "=== Dashboard ==="
    compose logs --tail 80 dashboard
}

show_dashboard_logs() {
    detect_docker_command
    compose logs --tail 200 -f dashboard
}

open_console() {
    if ! tmux_exists; then
        error "Fitness AI läuft nicht in der tmux-Session."
        exit 1
    fi
    tmux attach-session -t "$TMUX_SESSION"
}

show_usage() {
    echo
    echo "Verwendung:"
    echo
    echo "  $0 start"
    echo "  $0 stop"
    echo "  $0 restart"
    echo "  $0 status"
    echo "  $0 logs"
    echo "  $0 dashboard-logs"
    echo "  $0 console"
    echo
}

case "${1:-}" in
    start) start_all ;;
    stop) stop_all ;;
    restart) restart_all ;;
    status) show_status ;;
    logs) show_logs ;;
    dashboard-logs) show_dashboard_logs ;;
    console) open_console ;;
    *)
        show_usage
        exit 1
        ;;
esac
