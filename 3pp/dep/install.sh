#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

GOBIN= GOROOT= GOCACHE= GOPATH=`pwd` go build github.com/golang/dep/cmd/dep
cp ./dep $PREFIX
