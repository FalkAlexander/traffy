#!/bin/sh
DIR="$HOME/traffy"
if [ ! -d "$DIR" ]; then
    mkdir -p $DIR
fi

ACCESS_LOGFILE="$DIR/web-access.log"
ERROR_LOGFILE="$DIR/web-error.log"

exec gunicorn3 -b :5000 -c hooks.py web:app


