# Generated by the pRPC protocol buffer compiler plugin.  DO NOT EDIT!
# source: api/api_proto/issues.proto

import base64
import zlib

from google.protobuf import descriptor_pb2

# Includes description of the api/api_proto/issues.proto and all of its transitive
# dependencies. Includes source code info.
FILE_DESCRIPTOR_SET = descriptor_pb2.FileDescriptorSet()
FILE_DESCRIPTOR_SET.ParseFromString(zlib.decompress(base64.b64decode(
    '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')))
_INDEX = {
    f.name: {
      'descriptor': f,
      'services': {s.name: s for s in f.service},
    }
    for f in FILE_DESCRIPTOR_SET.file
}


IssuesServiceDescription = {
  'file_descriptor_set': FILE_DESCRIPTOR_SET,
  'file_descriptor': _INDEX[u'api/api_proto/issues.proto']['descriptor'],
  'service_descriptor': _INDEX[u'api/api_proto/issues.proto']['services'][u'Issues'],
}
