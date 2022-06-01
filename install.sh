#!/bin/bash

#
#
#
#
#
#
#
#

if ! command -v python3 &> /dev/null
then
    echo "Python 3 is not installed/could not be found"
    exit
fi

python3 -m pip install -r requirements.txt  
python3 -c "from app import db; db.create_all()"
python3 app.py