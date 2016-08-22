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

def server_options(
    _multi_method_implementation=None, _request_deserializers=None,
    _response_serializers=None, _thread_pool=None, _thread_pool_size=None,
    _default_timeout=None, _maximum_timeout=None):
  raise NotImplementedError()


def server(_service_implementations, _options=None):
  raise NotImplementedError()


def stub_options(
    _host=None, _request_serializers=None, _response_deserializers=None,
    _metadata_transformer=None, _thread_pool=None, _thread_pool_size=None):
  raise NotImplementedError()


def dynamic_stub(_channel, _service, _cardinalities, _options=None):
  raise NotImplementedError()
