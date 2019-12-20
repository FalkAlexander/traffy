#!/bin/sh
DIR="$HOME/traffy"
if [ ! -d "$DIR" ]; then
    mkdir -p $DIR
fi

ACCESS_LOGFILE="$DIR/access.log"
ERROR_LOGFILE="$DIR/error.log"

# Development
exec gunicorn3 --threads 4 -b :5000 --access-logfile $ACCESS_LOGFILE --error-logfile $ERROR_LOGFILE traffy:app

# Production
# exec gunicorn3 --threads 4 -d -b :5000 --access-logfile $ACCESS_LOGFILE --error-logfile $ERROR_LOGFILE traffy:app


