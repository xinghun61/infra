# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by the Apache v2.0 license that can be
# found in the LICENSE file.

compile:
	echo Compiling .proto files
	protoc --python_out=. --prpc-python_out=. *.proto
	yapf -i *_pb2.py
