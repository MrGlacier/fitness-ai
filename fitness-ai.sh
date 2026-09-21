#!/usr/bin/env bash

set -Eeuo pipefail


# =============================================================================
# Fitness AI - tmux Start / Stop / Status / Console
#
# Verwendung:
#
#   ./fitness-ai.sh start
#   ./fitness-ai.sh stop
#   ./fitness-ai.sh restart
#   ./fitness-ai.sh status
#   ./fitness-ai.sh console
#
# tmux Layout:
#
#   +--------------------------------------+
#   | LLM                                  |
#   | llama-server                         |
#   +--------------------------------------+
#   | API                                  |
#   | FastAPI / uvicorn                    |
#   +--------------------------------------+
#   | WEBUI                                |
#   | docker logs -f open-webui            |
#   +--------------------------------------+
#
# tmux verlassen, ohne Prozesse zu stoppen:
#
#   Ctrl+B
#   danach D
# =============================================================================


# -----------------------------------------------------------------------------
# Konfiguration
# -----------------------------------------------------------------------------

PROJECT_DIR="/home/MrGlacier/_projects/fitness-ai"

#MODEL="/home/MrGlacier/.cache/llama.cpp/Qwen_Qwen3-14B-GGUF_Qwen3-14B-Q4_K_M.gguf"
MODEL="unsloth/Qwen3.6-35B-A3B-GGUF:UD-IQ4_NL"

TMUX_SESSION="fitness-ai"

OPEN_WEBUI_CONTAINER="open-webui"


# -----------------------------------------------------------------------------
# Ausgabe
# -----------------------------------------------------------------------------

function info() {
    echo "[INFO] $1"
}


function ok() {
    echo "[ OK ] $1"
}


function error() {
    echo "[ERROR] $1" >&2
}


# -----------------------------------------------------------------------------
# tmux
# -----------------------------------------------------------------------------

function tmux_exists() {
    tmux has-session -t "$TMUX_SESSION" 2>/dev/null
}


# -----------------------------------------------------------------------------
# Docker erkennen
#
# Falls Docker ohne sudo funktioniert:
#
#   docker
#
# ansonsten:
#
#   sudo docker
# -----------------------------------------------------------------------------

function detect_docker_command() {

    if docker info >/dev/null 2>&1; then
        DOCKER=(docker)
    else
        DOCKER=(sudo docker)
    fi
}


# -----------------------------------------------------------------------------
# Open WebUI starten
# -----------------------------------------------------------------------------

function start_open_webui() {

    detect_docker_command

    info "Prüfe Open-WebUI-Container..."


    # -------------------------------------------------------------------------
    # Container existiert bereits
    # -------------------------------------------------------------------------

    if "${DOCKER[@]}" inspect "$OPEN_WEBUI_CONTAINER" >/dev/null 2>&1; then

        if "${DOCKER[@]}" inspect \
            -f '{{.State.Running}}' \
            "$OPEN_WEBUI_CONTAINER" 2>/dev/null | grep -q true; then

            ok "Open WebUI läuft bereits."
            return
        fi


        info "Starte vorhandenen Open-WebUI-Container..."

        "${DOCKER[@]}" start "$OPEN_WEBUI_CONTAINER" >/dev/null

        ok "Open WebUI gestartet."

        return
    fi


    # -------------------------------------------------------------------------
    # Container existiert noch nicht
    #
    # docker run lädt das Image automatisch herunter, falls es fehlt.
    # -------------------------------------------------------------------------

    info "Open WebUI ist noch nicht eingerichtet."
    info "Lade Open WebUI herunter und erstelle Container..."


    "${DOCKER[@]}" run -d \
        -p 3000:8080 \
        --add-host=host.docker.internal:host-gateway \
        -v open-webui:/app/backend/data \
        --name "$OPEN_WEBUI_CONTAINER" \
        --restart always \
        ghcr.io/open-webui/open-webui:main


    ok "Open WebUI wurde eingerichtet und gestartet."
}


# -----------------------------------------------------------------------------
# tmux Session starten
# -----------------------------------------------------------------------------

function start_tmux() {

    if tmux_exists; then
        ok "tmux Session '$TMUX_SESSION' läuft bereits."
        return
    fi


    info "Erstelle tmux Session '$TMUX_SESSION'..."


    # =========================================================================
    # Pane 1 - LLM
    # =========================================================================

    tmux new-session \
        -d \
        -s "$TMUX_SESSION" \
        -n "fitness-ai" \
        -c "$PROJECT_DIR" \
        "llama-server \
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


    # =========================================================================
    # Pane 2 - API
    # =========================================================================

    tmux split-window \
        -v \
        -t "$TMUX_SESSION:0" \
        -c "$PROJECT_DIR" \
        "PYTHONPATH=. uv run uvicorn api:app \
            --host 0.0.0.0 \
            --port 8000 \
            --reload"


    # =========================================================================
    # Pane 3 - Open WebUI Logs
    # =========================================================================

    detect_docker_command

    if [[ "${DOCKER[0]}" == "sudo" ]]; then
        DOCKER_LOG_COMMAND="sudo docker logs -f '$OPEN_WEBUI_CONTAINER'"
    else
        DOCKER_LOG_COMMAND="docker logs -f '$OPEN_WEBUI_CONTAINER'"
    fi


    tmux split-window \
        -v \
        -t "$TMUX_SESSION:0" \
        -c "$PROJECT_DIR" \
        "$DOCKER_LOG_COMMAND"


    # =========================================================================
    # Layout
    #
    # even-vertical verteilt alle drei Panes gleichmäßig untereinander.
    # =========================================================================

    tmux select-layout \
        -t "$TMUX_SESSION:0" \
        even-vertical


    # =========================================================================
    # Pane-Titel setzen
    # =========================================================================

    tmux select-pane -t "$TMUX_SESSION:0.0" -T "LLM"
    tmux select-pane -t "$TMUX_SESSION:0.1" -T "API"
    tmux select-pane -t "$TMUX_SESSION:0.2" -T "Open WebUI"


    # Pane-Titel sichtbar machen
    tmux set-option \
        -t "$TMUX_SESSION" \
        pane-border-status top


    # Aktives Pane wieder auf LLM setzen
    tmux select-pane \
        -t "$TMUX_SESSION:0.0"


    ok "tmux Session '$TMUX_SESSION' erstellt."
}


# -----------------------------------------------------------------------------
# Alles starten
# -----------------------------------------------------------------------------

function start_all() {

    echo
    echo "========================================"
    echo " Fitness AI starten"
    echo "========================================"
    echo


    # Open WebUI zuerst starten, damit docker logs danach funktioniert.
    start_open_webui

    start_tmux


    echo
    echo "========================================"
    echo " Fitness AI läuft"
    echo "========================================"
    echo

    echo "Open WebUI:"
    echo "  http://localhost:3000"

    echo
    echo "Fitness API:"
    echo "  http://localhost:8000"

    echo
    echo "LLM:"
    echo "  http://localhost:8080"

    echo
    echo "Console:"
    echo "  ./fitness-ai.sh console"

    echo
}


# -----------------------------------------------------------------------------
# Alles stoppen
# -----------------------------------------------------------------------------

function stop_all() {

    echo
    echo "========================================"
    echo " Fitness AI stoppen"
    echo "========================================"
    echo


    # -------------------------------------------------------------------------
    # tmux Session stoppen
    #
    # Dadurch werden llama-server, uvicorn und docker logs beendet.
    # -------------------------------------------------------------------------

    if tmux_exists; then

        info "Stoppe tmux Session '$TMUX_SESSION'..."

        tmux kill-session -t "$TMUX_SESSION"

        ok "LLM und Fitness API gestoppt."

    else

        info "tmux Session '$TMUX_SESSION' läuft nicht."

    fi


    # -------------------------------------------------------------------------
    # Open WebUI stoppen
    # -------------------------------------------------------------------------

    detect_docker_command


    if "${DOCKER[@]}" inspect "$OPEN_WEBUI_CONTAINER" >/dev/null 2>&1; then

        if "${DOCKER[@]}" inspect \
            -f '{{.State.Running}}' \
            "$OPEN_WEBUI_CONTAINER" 2>/dev/null | grep -q true; then


            info "Stoppe Open WebUI..."

            "${DOCKER[@]}" stop "$OPEN_WEBUI_CONTAINER" >/dev/null

            ok "Open WebUI gestoppt."

        else

            info "Open WebUI läuft nicht."

        fi

    else

        info "Open-WebUI-Container existiert nicht."

    fi


    echo
    ok "Fitness AI gestoppt."
    echo
}


# -----------------------------------------------------------------------------
# Status
# -----------------------------------------------------------------------------

function show_status() {

    echo
    echo "========================================"
    echo " Fitness AI Status"
    echo "========================================"
    echo


    # -------------------------------------------------------------------------
    # tmux
    # -------------------------------------------------------------------------

    if tmux_exists; then
        echo "LLM / API:    RUNNING"
    else
        echo "LLM / API:    STOPPED"
    fi


    # -------------------------------------------------------------------------
    # Open WebUI
    # -------------------------------------------------------------------------

    detect_docker_command


    if "${DOCKER[@]}" inspect "$OPEN_WEBUI_CONTAINER" >/dev/null 2>&1; then

        if "${DOCKER[@]}" inspect \
            -f '{{.State.Running}}' \
            "$OPEN_WEBUI_CONTAINER" 2>/dev/null | grep -q true; then

            echo "Open WebUI:   RUNNING"

        else

            echo "Open WebUI:   STOPPED"

        fi

    else

        echo "Open WebUI:   NOT INSTALLED"

    fi


    echo
}


# -----------------------------------------------------------------------------
# Console öffnen
# -----------------------------------------------------------------------------

function open_console() {

    if ! tmux_exists; then

        error "Fitness AI läuft nicht."

        echo
        echo "Starte sie zuerst mit:"
        echo
        echo "  $0 start"
        echo

        exit 1
    fi


    tmux attach-session -t "$TMUX_SESSION"
}


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

case "${1:-}" in

    start)
        start_all
        ;;

    stop)
        stop_all
        ;;

    restart)
        stop_all
        start_all
        ;;

    status)
        show_status
        ;;

    console)
        open_console
        ;;

    *)
        echo
        echo "Verwendung:"
        echo
        echo "  $0 start"
        echo "  $0 stop"
        echo "  $0 restart"
        echo "  $0 status"
        echo "  $0 console"
        echo
        exit 1
        ;;

esac