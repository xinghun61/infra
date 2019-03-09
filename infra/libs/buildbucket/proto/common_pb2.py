# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: common.proto

import sys
_b = sys.version_info[0] < 3 and (lambda x: x) or (lambda x: x.encode('latin1'))
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()

from google.protobuf import duration_pb2 as google_dot_protobuf_dot_duration__pb2
from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2

DESCRIPTOR = _descriptor.FileDescriptor(
    name='common.proto',
    package='buildbucket.v2',
    syntax='proto3',
    serialized_options=_b(
        'Z4go.chromium.org/luci/buildbucket/proto;buildbucketpb'
    ),
    serialized_pb=_b(
        '\n\x0c\x63ommon.proto\x12\x0e\x62uildbucket.v2\x1a\x1egoogle/protobuf/duration.proto\x1a\x1fgoogle/protobuf/timestamp.proto\"O\n\x0cGerritChange\x12\x0c\n\x04host\x18\x01 \x01(\t\x12\x0f\n\x07project\x18\x02 \x01(\t\x12\x0e\n\x06\x63hange\x18\x03 \x01(\x03\x12\x10\n\x08patchset\x18\x04 \x01(\x03\"Y\n\rGitilesCommit\x12\x0c\n\x04host\x18\x01 \x01(\t\x12\x0f\n\x07project\x18\x02 \x01(\t\x12\n\n\x02id\x18\x03 \x01(\t\x12\x0b\n\x03ref\x18\x04 \x01(\t\x12\x10\n\x08position\x18\x05 \x01(\r\"(\n\nStringPair\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t\"i\n\tTimeRange\x12.\n\nstart_time\x18\x01 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12,\n\x08\x65nd_time\x18\x02 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\"_\n\x12RequestedDimension\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t\x12-\n\nexpiration\x18\x03 \x01(\x0b\x32\x19.google.protobuf.Duration*\x87\x01\n\x06Status\x12\x16\n\x12STATUS_UNSPECIFIED\x10\x00\x12\r\n\tSCHEDULED\x10\x01\x12\x0b\n\x07STARTED\x10\x02\x12\x0e\n\nENDED_MASK\x10\x04\x12\x0b\n\x07SUCCESS\x10\x0c\x12\x0b\n\x07\x46\x41ILURE\x10\x14\x12\x11\n\rINFRA_FAILURE\x10$\x12\x0c\n\x08\x43\x41NCELED\x10\x44*%\n\x07Trinary\x12\t\n\x05UNSET\x10\x00\x12\x07\n\x03YES\x10\x01\x12\x06\n\x02NO\x10\x02\x42\x36Z4go.chromium.org/luci/buildbucket/proto;buildbucketpbb\x06proto3'
    ),
    dependencies=[
        google_dot_protobuf_dot_duration__pb2.DESCRIPTOR,
        google_dot_protobuf_dot_timestamp__pb2.DESCRIPTOR,
    ]
)

_STATUS = _descriptor.EnumDescriptor(
    name='Status',
    full_name='buildbucket.v2.Status',
    filename=None,
    file=DESCRIPTOR,
    values=[
        _descriptor.EnumValueDescriptor(
            name='STATUS_UNSPECIFIED',
            index=0,
            number=0,
            serialized_options=None,
            type=None
        ),
        _descriptor.EnumValueDescriptor(
            name='SCHEDULED',
            index=1,
            number=1,
            serialized_options=None,
            type=None
        ),
        _descriptor.EnumValueDescriptor(
            name='STARTED',
            index=2,
            number=2,
            serialized_options=None,
            type=None
        ),
        _descriptor.EnumValueDescriptor(
            name='ENDED_MASK',
            index=3,
            number=4,
            serialized_options=None,
            type=None
        ),
        _descriptor.EnumValueDescriptor(
            name='SUCCESS',
            index=4,
            number=12,
            serialized_options=None,
            type=None
        ),
        _descriptor.EnumValueDescriptor(
            name='FAILURE',
            index=5,
            number=20,
            serialized_options=None,
            type=None
        ),
        _descriptor.EnumValueDescriptor(
            name='INFRA_FAILURE',
            index=6,
            number=36,
            serialized_options=None,
            type=None
        ),
        _descriptor.EnumValueDescriptor(
            name='CANCELED',
            index=7,
            number=68,
            serialized_options=None,
            type=None
        ),
    ],
    containing_type=None,
    serialized_options=None,
    serialized_start=516,
    serialized_end=651,
)
_sym_db.RegisterEnumDescriptor(_STATUS)

Status = enum_type_wrapper.EnumTypeWrapper(_STATUS)
_TRINARY = _descriptor.EnumDescriptor(
    name='Trinary',
    full_name='buildbucket.v2.Trinary',
    filename=None,
    file=DESCRIPTOR,
    values=[
        _descriptor.EnumValueDescriptor(
            name='UNSET', index=0, number=0, serialized_options=None, type=None
        ),
        _descriptor.EnumValueDescriptor(
            name='YES', index=1, number=1, serialized_options=None, type=None
        ),
        _descriptor.EnumValueDescriptor(
            name='NO', index=2, number=2, serialized_options=None, type=None
        ),
    ],
    containing_type=None,
    serialized_options=None,
    serialized_start=653,
    serialized_end=690,
)
_sym_db.RegisterEnumDescriptor(_TRINARY)

Trinary = enum_type_wrapper.EnumTypeWrapper(_TRINARY)
STATUS_UNSPECIFIED = 0
SCHEDULED = 1
STARTED = 2
ENDED_MASK = 4
SUCCESS = 12
FAILURE = 20
INFRA_FAILURE = 36
CANCELED = 68
UNSET = 0
YES = 1
NO = 2

_GERRITCHANGE = _descriptor.Descriptor(
    name='GerritChange',
    full_name='buildbucket.v2.GerritChange',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    fields=[
        _descriptor.FieldDescriptor(
            name='host',
            full_name='buildbucket.v2.GerritChange.host',
            index=0,
            number=1,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=_b("").decode('utf-8'),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='project',
            full_name='buildbucket.v2.GerritChange.project',
            index=1,
            number=2,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=_b("").decode('utf-8'),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='change',
            full_name='buildbucket.v2.GerritChange.change',
            index=2,
            number=3,
            type=3,
            cpp_type=2,
            label=1,
            has_default_value=False,
            default_value=0,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='patchset',
            full_name='buildbucket.v2.GerritChange.patchset',
            index=3,
            number=4,
            type=3,
            cpp_type=2,
            label=1,
            has_default_value=False,
            default_value=0,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax='proto3',
    extension_ranges=[],
    oneofs=[],
    serialized_start=97,
    serialized_end=176,
)

_GITILESCOMMIT = _descriptor.Descriptor(
    name='GitilesCommit',
    full_name='buildbucket.v2.GitilesCommit',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    fields=[
        _descriptor.FieldDescriptor(
            name='host',
            full_name='buildbucket.v2.GitilesCommit.host',
            index=0,
            number=1,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=_b("").decode('utf-8'),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='project',
            full_name='buildbucket.v2.GitilesCommit.project',
            index=1,
            number=2,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=_b("").decode('utf-8'),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='id',
            full_name='buildbucket.v2.GitilesCommit.id',
            index=2,
            number=3,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=_b("").decode('utf-8'),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='ref',
            full_name='buildbucket.v2.GitilesCommit.ref',
            index=3,
            number=4,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=_b("").decode('utf-8'),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='position',
            full_name='buildbucket.v2.GitilesCommit.position',
            index=4,
            number=5,
            type=13,
            cpp_type=3,
            label=1,
            has_default_value=False,
            default_value=0,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax='proto3',
    extension_ranges=[],
    oneofs=[],
    serialized_start=178,
    serialized_end=267,
)

_STRINGPAIR = _descriptor.Descriptor(
    name='StringPair',
    full_name='buildbucket.v2.StringPair',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    fields=[
        _descriptor.FieldDescriptor(
            name='key',
            full_name='buildbucket.v2.StringPair.key',
            index=0,
            number=1,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=_b("").decode('utf-8'),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='value',
            full_name='buildbucket.v2.StringPair.value',
            index=1,
            number=2,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=_b("").decode('utf-8'),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax='proto3',
    extension_ranges=[],
    oneofs=[],
    serialized_start=269,
    serialized_end=309,
)

_TIMERANGE = _descriptor.Descriptor(
    name='TimeRange',
    full_name='buildbucket.v2.TimeRange',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    fields=[
        _descriptor.FieldDescriptor(
            name='start_time',
            full_name='buildbucket.v2.TimeRange.start_time',
            index=0,
            number=1,
            type=11,
            cpp_type=10,
            label=1,
            has_default_value=False,
            default_value=None,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='end_time',
            full_name='buildbucket.v2.TimeRange.end_time',
            index=1,
            number=2,
            type=11,
            cpp_type=10,
            label=1,
            has_default_value=False,
            default_value=None,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax='proto3',
    extension_ranges=[],
    oneofs=[],
    serialized_start=311,
    serialized_end=416,
)

_REQUESTEDDIMENSION = _descriptor.Descriptor(
    name='RequestedDimension',
    full_name='buildbucket.v2.RequestedDimension',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    fields=[
        _descriptor.FieldDescriptor(
            name='key',
            full_name='buildbucket.v2.RequestedDimension.key',
            index=0,
            number=1,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=_b("").decode('utf-8'),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='value',
            full_name='buildbucket.v2.RequestedDimension.value',
            index=1,
            number=2,
            type=9,
            cpp_type=9,
            label=1,
            has_default_value=False,
            default_value=_b("").decode('utf-8'),
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
        _descriptor.FieldDescriptor(
            name='expiration',
            full_name='buildbucket.v2.RequestedDimension.expiration',
            index=2,
            number=3,
            type=11,
            cpp_type=10,
            label=1,
            has_default_value=False,
            default_value=None,
            message_type=None,
            enum_type=None,
            containing_type=None,
            is_extension=False,
            extension_scope=None,
            serialized_options=None,
            file=DESCRIPTOR
        ),
    ],
    extensions=[],
    nested_types=[],
    enum_types=[],
    serialized_options=None,
    is_extendable=False,
    syntax='proto3',
    extension_ranges=[],
    oneofs=[],
    serialized_start=418,
    serialized_end=513,
)

_TIMERANGE.fields_by_name[
    'start_time'
].message_type = google_dot_protobuf_dot_timestamp__pb2._TIMESTAMP
_TIMERANGE.fields_by_name[
    'end_time'].message_type = google_dot_protobuf_dot_timestamp__pb2._TIMESTAMP
_REQUESTEDDIMENSION.fields_by_name[
    'expiration'].message_type = google_dot_protobuf_dot_duration__pb2._DURATION
DESCRIPTOR.message_types_by_name['GerritChange'] = _GERRITCHANGE
DESCRIPTOR.message_types_by_name['GitilesCommit'] = _GITILESCOMMIT
DESCRIPTOR.message_types_by_name['StringPair'] = _STRINGPAIR
DESCRIPTOR.message_types_by_name['TimeRange'] = _TIMERANGE
DESCRIPTOR.message_types_by_name['RequestedDimension'] = _REQUESTEDDIMENSION
DESCRIPTOR.enum_types_by_name['Status'] = _STATUS
DESCRIPTOR.enum_types_by_name['Trinary'] = _TRINARY
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

GerritChange = _reflection.GeneratedProtocolMessageType(
    'GerritChange',
    (_message.Message,),
    dict(
        DESCRIPTOR=_GERRITCHANGE,
        __module__='common_pb2'
        # @@protoc_insertion_point(class_scope:buildbucket.v2.GerritChange)
    )
)
_sym_db.RegisterMessage(GerritChange)

GitilesCommit = _reflection.GeneratedProtocolMessageType(
    'GitilesCommit',
    (_message.Message,),
    dict(
        DESCRIPTOR=_GITILESCOMMIT,
        __module__='common_pb2'
        # @@protoc_insertion_point(class_scope:buildbucket.v2.GitilesCommit)
    )
)
_sym_db.RegisterMessage(GitilesCommit)

StringPair = _reflection.GeneratedProtocolMessageType(
    'StringPair',
    (_message.Message,),
    dict(
        DESCRIPTOR=_STRINGPAIR,
        __module__='common_pb2'
        # @@protoc_insertion_point(class_scope:buildbucket.v2.StringPair)
    )
)
_sym_db.RegisterMessage(StringPair)

TimeRange = _reflection.GeneratedProtocolMessageType(
    'TimeRange',
    (_message.Message,),
    dict(
        DESCRIPTOR=_TIMERANGE,
        __module__='common_pb2'
        # @@protoc_insertion_point(class_scope:buildbucket.v2.TimeRange)
    )
)
_sym_db.RegisterMessage(TimeRange)

RequestedDimension = _reflection.GeneratedProtocolMessageType(
    'RequestedDimension',
    (_message.Message,),
    dict(
        DESCRIPTOR=_REQUESTEDDIMENSION,
        __module__='common_pb2'
        # @@protoc_insertion_point(class_scope:buildbucket.v2.RequestedDimension)
    )
)
_sym_db.RegisterMessage(RequestedDimension)

DESCRIPTOR._options = None
# @@protoc_insertion_point(module_scope)
