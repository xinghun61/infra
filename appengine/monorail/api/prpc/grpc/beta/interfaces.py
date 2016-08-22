# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""This file exists so that code in gRPC *_pb2.py files is importable.

The protoc compiler for gRPC .proto files produces Python code which contains
two separate code-paths. One codepath just requires importing grpc.py; the
other uses the beta interface. Since we are relying on the former codepath,
this file doesn't need to contain any actual implementation. It just needs
to contain the symbols that the _pb2.py file expects to find when it imports
the module.
"""

import grpc


StatusCode = grpc.StatusCode
