# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: api/api_proto/users.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from api.api_proto import user_objects_pb2 as api_dot_api__proto_dot_user__objects__pb2
from api.api_proto import common_pb2 as api_dot_api__proto_dot_common__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='api/api_proto/users.proto',
  package='monorail',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x19\x61pi/api_proto/users.proto\x12\x08monorail\x1a api/api_proto/user_objects.proto\x1a\x1a\x61pi/api_proto/common.proto\"=\n\x04User\x12\r\n\x05\x65mail\x18\x01 \x01(\t\x12\x0f\n\x07user_id\x18\x02 \x01(\x03\x12\x15\n\ris_site_admin\x18\x03 \x01(\x08\"S\n\x1aListReferencedUsersRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12\x0e\n\x06\x65mails\x18\x02 \x03(\t\"<\n\x1bListReferencedUsersResponse\x12\x1d\n\x05users\x18\x01 \x03(\x0b\x32\x0e.monorail.User\"\\\n\x0eGetUserRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12#\n\x08user_ref\x18\x02 \x01(\x0b\x32\x11.monorail.UserRef\"c\n\x15GetMembershipsRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12#\n\x08user_ref\x18\x02 \x01(\x0b\x32\x11.monorail.UserRef\"?\n\x16GetMembershipsResponse\x12%\n\ngroup_refs\x18\x01 \x03(\x0b\x32\x11.monorail.UserRef\"~\n\x15GetUserCommitsRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12\r\n\x05\x65mail\x18\x02 \x01(\t\x12\x16\n\x0e\x66rom_timestamp\x18\x03 \x01(\x07\x12\x17\n\x0funtil_timestamp\x18\x04 \x01(\x07\"@\n\x16GetUserCommitsResponse\x12&\n\x0cuser_commits\x18\x01 \x03(\x0b\x32\x10.monorail.Commit\"e\n\x17GetUserStarCountRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12#\n\x08user_ref\x18\x02 \x01(\x0b\x32\x11.monorail.UserRef\".\n\x18GetUserStarCountResponse\x12\x12\n\nstar_count\x18\x01 \x01(\r\"n\n\x0fStarUserRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12#\n\x08user_ref\x18\x02 \x01(\x0b\x32\x11.monorail.UserRef\x12\x0f\n\x07starred\x18\x03 \x01(\x08\"&\n\x10StarUserResponse\x12\x12\n\nstar_count\x18\x01 \x01(\r\"^\n\x1fSetExpandPermsPreferenceRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12\x14\n\x0c\x65xpand_perms\x18\x02 \x01(\x08\"\"\n SetExpandPermsPreferenceResponse2\xe9\x04\n\x05Users\x12\x35\n\x07GetUser\x12\x18.monorail.GetUserRequest\x1a\x0e.monorail.User\"\x00\x12\x64\n\x13ListReferencedUsers\x12$.monorail.ListReferencedUsersRequest\x1a%.monorail.ListReferencedUsersResponse\"\x00\x12U\n\x0eGetMemberships\x12\x1f.monorail.GetMembershipsRequest\x1a .monorail.GetMembershipsResponse\"\x00\x12U\n\x0eGetUserCommits\x12\x1f.monorail.GetUserCommitsRequest\x1a .monorail.GetUserCommitsResponse\"\x00\x12[\n\x10GetUserStarCount\x12!.monorail.GetUserStarCountRequest\x1a\".monorail.GetUserStarCountResponse\"\x00\x12\x43\n\x08StarUser\x12\x19.monorail.StarUserRequest\x1a\x1a.monorail.StarUserResponse\"\x00\x12s\n\x18SetExpandPermsPreference\x12).monorail.SetExpandPermsPreferenceRequest\x1a*.monorail.SetExpandPermsPreferenceResponse\"\x00\x62\x06proto3')
  ,
  dependencies=[api_dot_api__proto_dot_user__objects__pb2.DESCRIPTOR,api_dot_api__proto_dot_common__pb2.DESCRIPTOR,])




_USER = _descriptor.Descriptor(
  name='User',
  full_name='monorail.User',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='email', full_name='monorail.User.email', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='user_id', full_name='monorail.User.user_id', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='is_site_admin', full_name='monorail.User.is_site_admin', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=101,
  serialized_end=162,
)


_LISTREFERENCEDUSERSREQUEST = _descriptor.Descriptor(
  name='ListReferencedUsersRequest',
  full_name='monorail.ListReferencedUsersRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.ListReferencedUsersRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='emails', full_name='monorail.ListReferencedUsersRequest.emails', index=1,
      number=2, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=164,
  serialized_end=247,
)


_LISTREFERENCEDUSERSRESPONSE = _descriptor.Descriptor(
  name='ListReferencedUsersResponse',
  full_name='monorail.ListReferencedUsersResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='users', full_name='monorail.ListReferencedUsersResponse.users', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=249,
  serialized_end=309,
)


_GETUSERREQUEST = _descriptor.Descriptor(
  name='GetUserRequest',
  full_name='monorail.GetUserRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.GetUserRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='user_ref', full_name='monorail.GetUserRequest.user_ref', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=311,
  serialized_end=403,
)


_GETMEMBERSHIPSREQUEST = _descriptor.Descriptor(
  name='GetMembershipsRequest',
  full_name='monorail.GetMembershipsRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.GetMembershipsRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='user_ref', full_name='monorail.GetMembershipsRequest.user_ref', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=405,
  serialized_end=504,
)


_GETMEMBERSHIPSRESPONSE = _descriptor.Descriptor(
  name='GetMembershipsResponse',
  full_name='monorail.GetMembershipsResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='group_refs', full_name='monorail.GetMembershipsResponse.group_refs', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=506,
  serialized_end=569,
)


_GETUSERCOMMITSREQUEST = _descriptor.Descriptor(
  name='GetUserCommitsRequest',
  full_name='monorail.GetUserCommitsRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.GetUserCommitsRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='email', full_name='monorail.GetUserCommitsRequest.email', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='from_timestamp', full_name='monorail.GetUserCommitsRequest.from_timestamp', index=2,
      number=3, type=7, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='until_timestamp', full_name='monorail.GetUserCommitsRequest.until_timestamp', index=3,
      number=4, type=7, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=571,
  serialized_end=697,
)


_GETUSERCOMMITSRESPONSE = _descriptor.Descriptor(
  name='GetUserCommitsResponse',
  full_name='monorail.GetUserCommitsResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='user_commits', full_name='monorail.GetUserCommitsResponse.user_commits', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=699,
  serialized_end=763,
)


_GETUSERSTARCOUNTREQUEST = _descriptor.Descriptor(
  name='GetUserStarCountRequest',
  full_name='monorail.GetUserStarCountRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.GetUserStarCountRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='user_ref', full_name='monorail.GetUserStarCountRequest.user_ref', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=765,
  serialized_end=866,
)


_GETUSERSTARCOUNTRESPONSE = _descriptor.Descriptor(
  name='GetUserStarCountResponse',
  full_name='monorail.GetUserStarCountResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='star_count', full_name='monorail.GetUserStarCountResponse.star_count', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=868,
  serialized_end=914,
)


_STARUSERREQUEST = _descriptor.Descriptor(
  name='StarUserRequest',
  full_name='monorail.StarUserRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.StarUserRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='user_ref', full_name='monorail.StarUserRequest.user_ref', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='starred', full_name='monorail.StarUserRequest.starred', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=916,
  serialized_end=1026,
)


_STARUSERRESPONSE = _descriptor.Descriptor(
  name='StarUserResponse',
  full_name='monorail.StarUserResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='star_count', full_name='monorail.StarUserResponse.star_count', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1028,
  serialized_end=1066,
)


_SETEXPANDPERMSPREFERENCEREQUEST = _descriptor.Descriptor(
  name='SetExpandPermsPreferenceRequest',
  full_name='monorail.SetExpandPermsPreferenceRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.SetExpandPermsPreferenceRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='expand_perms', full_name='monorail.SetExpandPermsPreferenceRequest.expand_perms', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1068,
  serialized_end=1162,
)


_SETEXPANDPERMSPREFERENCERESPONSE = _descriptor.Descriptor(
  name='SetExpandPermsPreferenceResponse',
  full_name='monorail.SetExpandPermsPreferenceResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1164,
  serialized_end=1198,
)

_LISTREFERENCEDUSERSREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_LISTREFERENCEDUSERSRESPONSE.fields_by_name['users'].message_type = _USER
_GETUSERREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_GETUSERREQUEST.fields_by_name['user_ref'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_GETMEMBERSHIPSREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_GETMEMBERSHIPSREQUEST.fields_by_name['user_ref'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_GETMEMBERSHIPSRESPONSE.fields_by_name['group_refs'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_GETUSERCOMMITSREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_GETUSERCOMMITSRESPONSE.fields_by_name['user_commits'].message_type = api_dot_api__proto_dot_user__objects__pb2._COMMIT
_GETUSERSTARCOUNTREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_GETUSERSTARCOUNTREQUEST.fields_by_name['user_ref'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_STARUSERREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_STARUSERREQUEST.fields_by_name['user_ref'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_SETEXPANDPERMSPREFERENCEREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
DESCRIPTOR.message_types_by_name['User'] = _USER
DESCRIPTOR.message_types_by_name['ListReferencedUsersRequest'] = _LISTREFERENCEDUSERSREQUEST
DESCRIPTOR.message_types_by_name['ListReferencedUsersResponse'] = _LISTREFERENCEDUSERSRESPONSE
DESCRIPTOR.message_types_by_name['GetUserRequest'] = _GETUSERREQUEST
DESCRIPTOR.message_types_by_name['GetMembershipsRequest'] = _GETMEMBERSHIPSREQUEST
DESCRIPTOR.message_types_by_name['GetMembershipsResponse'] = _GETMEMBERSHIPSRESPONSE
DESCRIPTOR.message_types_by_name['GetUserCommitsRequest'] = _GETUSERCOMMITSREQUEST
DESCRIPTOR.message_types_by_name['GetUserCommitsResponse'] = _GETUSERCOMMITSRESPONSE
DESCRIPTOR.message_types_by_name['GetUserStarCountRequest'] = _GETUSERSTARCOUNTREQUEST
DESCRIPTOR.message_types_by_name['GetUserStarCountResponse'] = _GETUSERSTARCOUNTRESPONSE
DESCRIPTOR.message_types_by_name['StarUserRequest'] = _STARUSERREQUEST
DESCRIPTOR.message_types_by_name['StarUserResponse'] = _STARUSERRESPONSE
DESCRIPTOR.message_types_by_name['SetExpandPermsPreferenceRequest'] = _SETEXPANDPERMSPREFERENCEREQUEST
DESCRIPTOR.message_types_by_name['SetExpandPermsPreferenceResponse'] = _SETEXPANDPERMSPREFERENCERESPONSE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

User = _reflection.GeneratedProtocolMessageType('User', (_message.Message,), dict(
  DESCRIPTOR = _USER,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.User)
  ))
_sym_db.RegisterMessage(User)

ListReferencedUsersRequest = _reflection.GeneratedProtocolMessageType('ListReferencedUsersRequest', (_message.Message,), dict(
  DESCRIPTOR = _LISTREFERENCEDUSERSREQUEST,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.ListReferencedUsersRequest)
  ))
_sym_db.RegisterMessage(ListReferencedUsersRequest)

ListReferencedUsersResponse = _reflection.GeneratedProtocolMessageType('ListReferencedUsersResponse', (_message.Message,), dict(
  DESCRIPTOR = _LISTREFERENCEDUSERSRESPONSE,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.ListReferencedUsersResponse)
  ))
_sym_db.RegisterMessage(ListReferencedUsersResponse)

GetUserRequest = _reflection.GeneratedProtocolMessageType('GetUserRequest', (_message.Message,), dict(
  DESCRIPTOR = _GETUSERREQUEST,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.GetUserRequest)
  ))
_sym_db.RegisterMessage(GetUserRequest)

GetMembershipsRequest = _reflection.GeneratedProtocolMessageType('GetMembershipsRequest', (_message.Message,), dict(
  DESCRIPTOR = _GETMEMBERSHIPSREQUEST,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.GetMembershipsRequest)
  ))
_sym_db.RegisterMessage(GetMembershipsRequest)

GetMembershipsResponse = _reflection.GeneratedProtocolMessageType('GetMembershipsResponse', (_message.Message,), dict(
  DESCRIPTOR = _GETMEMBERSHIPSRESPONSE,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.GetMembershipsResponse)
  ))
_sym_db.RegisterMessage(GetMembershipsResponse)

GetUserCommitsRequest = _reflection.GeneratedProtocolMessageType('GetUserCommitsRequest', (_message.Message,), dict(
  DESCRIPTOR = _GETUSERCOMMITSREQUEST,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.GetUserCommitsRequest)
  ))
_sym_db.RegisterMessage(GetUserCommitsRequest)

GetUserCommitsResponse = _reflection.GeneratedProtocolMessageType('GetUserCommitsResponse', (_message.Message,), dict(
  DESCRIPTOR = _GETUSERCOMMITSRESPONSE,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.GetUserCommitsResponse)
  ))
_sym_db.RegisterMessage(GetUserCommitsResponse)

GetUserStarCountRequest = _reflection.GeneratedProtocolMessageType('GetUserStarCountRequest', (_message.Message,), dict(
  DESCRIPTOR = _GETUSERSTARCOUNTREQUEST,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.GetUserStarCountRequest)
  ))
_sym_db.RegisterMessage(GetUserStarCountRequest)

GetUserStarCountResponse = _reflection.GeneratedProtocolMessageType('GetUserStarCountResponse', (_message.Message,), dict(
  DESCRIPTOR = _GETUSERSTARCOUNTRESPONSE,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.GetUserStarCountResponse)
  ))
_sym_db.RegisterMessage(GetUserStarCountResponse)

StarUserRequest = _reflection.GeneratedProtocolMessageType('StarUserRequest', (_message.Message,), dict(
  DESCRIPTOR = _STARUSERREQUEST,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.StarUserRequest)
  ))
_sym_db.RegisterMessage(StarUserRequest)

StarUserResponse = _reflection.GeneratedProtocolMessageType('StarUserResponse', (_message.Message,), dict(
  DESCRIPTOR = _STARUSERRESPONSE,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.StarUserResponse)
  ))
_sym_db.RegisterMessage(StarUserResponse)

SetExpandPermsPreferenceRequest = _reflection.GeneratedProtocolMessageType('SetExpandPermsPreferenceRequest', (_message.Message,), dict(
  DESCRIPTOR = _SETEXPANDPERMSPREFERENCEREQUEST,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.SetExpandPermsPreferenceRequest)
  ))
_sym_db.RegisterMessage(SetExpandPermsPreferenceRequest)

SetExpandPermsPreferenceResponse = _reflection.GeneratedProtocolMessageType('SetExpandPermsPreferenceResponse', (_message.Message,), dict(
  DESCRIPTOR = _SETEXPANDPERMSPREFERENCERESPONSE,
  __module__ = 'api.api_proto.users_pb2'
  # @@protoc_insertion_point(class_scope:monorail.SetExpandPermsPreferenceResponse)
  ))
_sym_db.RegisterMessage(SetExpandPermsPreferenceResponse)



_USERS = _descriptor.ServiceDescriptor(
  name='Users',
  full_name='monorail.Users',
  file=DESCRIPTOR,
  index=0,
  serialized_options=None,
  serialized_start=1201,
  serialized_end=1818,
  methods=[
  _descriptor.MethodDescriptor(
    name='GetUser',
    full_name='monorail.Users.GetUser',
    index=0,
    containing_service=None,
    input_type=_GETUSERREQUEST,
    output_type=_USER,
    serialized_options=None,
  ),
  _descriptor.MethodDescriptor(
    name='ListReferencedUsers',
    full_name='monorail.Users.ListReferencedUsers',
    index=1,
    containing_service=None,
    input_type=_LISTREFERENCEDUSERSREQUEST,
    output_type=_LISTREFERENCEDUSERSRESPONSE,
    serialized_options=None,
  ),
  _descriptor.MethodDescriptor(
    name='GetMemberships',
    full_name='monorail.Users.GetMemberships',
    index=2,
    containing_service=None,
    input_type=_GETMEMBERSHIPSREQUEST,
    output_type=_GETMEMBERSHIPSRESPONSE,
    serialized_options=None,
  ),
  _descriptor.MethodDescriptor(
    name='GetUserCommits',
    full_name='monorail.Users.GetUserCommits',
    index=3,
    containing_service=None,
    input_type=_GETUSERCOMMITSREQUEST,
    output_type=_GETUSERCOMMITSRESPONSE,
    serialized_options=None,
  ),
  _descriptor.MethodDescriptor(
    name='GetUserStarCount',
    full_name='monorail.Users.GetUserStarCount',
    index=4,
    containing_service=None,
    input_type=_GETUSERSTARCOUNTREQUEST,
    output_type=_GETUSERSTARCOUNTRESPONSE,
    serialized_options=None,
  ),
  _descriptor.MethodDescriptor(
    name='StarUser',
    full_name='monorail.Users.StarUser',
    index=5,
    containing_service=None,
    input_type=_STARUSERREQUEST,
    output_type=_STARUSERRESPONSE,
    serialized_options=None,
  ),
  _descriptor.MethodDescriptor(
    name='SetExpandPermsPreference',
    full_name='monorail.Users.SetExpandPermsPreference',
    index=6,
    containing_service=None,
    input_type=_SETEXPANDPERMSPREFERENCEREQUEST,
    output_type=_SETEXPANDPERMSPREFERENCERESPONSE,
    serialized_options=None,
  ),
])
_sym_db.RegisterServiceDescriptor(_USERS)

DESCRIPTOR.services_by_name['Users'] = _USERS

# @@protoc_insertion_point(module_scope)
