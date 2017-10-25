#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export PYTHONPATH=$PYTHONPATH:$DIR/../../third_party
TMP_DIR=~/.crbadgepw
if [ -d ${TMP_DIR} ]; then
  mkdir ${TMP_DIR}
fi
#python $1
python $@ > ~/.crbadge-data
python $DIR/../../testdata/upload.py -p `${TMP_DIR}` -u https://crbadge.appspot.com/system/update ~/.crbadge-data
