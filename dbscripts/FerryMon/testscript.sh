#!/bin/bash
set -x

if psql --host="wave.ims.unc.edu" --port=5432 --username=postgres -lqt | cut -d \| -f 1 | grep -qw `hostname`; then
    echo database exists
else
    echo database does not exist
fi
