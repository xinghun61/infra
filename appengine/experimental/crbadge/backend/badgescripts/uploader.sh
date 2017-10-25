#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export PYTHONPATH=$PYTHONPATH:$DIR/../../third_party
python $DIR/../../testdata/upload.py -p `cat ~/.crbadgepw` -u https://crbadge.appspot.com/system/update >(python $@)
