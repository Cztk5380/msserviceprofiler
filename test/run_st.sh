
SCRIPT_DIR=$(realpath "$(dirname "$0")")
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

cd "$SCRIPT_DIR/st/collect"
python -m unittest discover