#!/bin/bash

# TODO(nbharadwaj) merge deploy and serve_dev

appcfg.py --oauth2 update api.yaml log.yaml
appcfg.py --oauth2 update_indexes -A unnamed-ci .
