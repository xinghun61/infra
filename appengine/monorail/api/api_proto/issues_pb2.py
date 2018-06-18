# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: api/api_proto/issues.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2
from google.protobuf import wrappers_pb2 as google_dot_protobuf_dot_wrappers__pb2
from api.api_proto import common_pb2 as api_dot_api__proto_dot_common__pb2
from api.api_proto import issue_objects_pb2 as api_dot_api__proto_dot_issue__objects__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='api/api_proto/issues.proto',
  package='monorail',
  syntax='proto3',
  serialized_pb=_b('\n\x1a\x61pi/api_proto/issues.proto\x12\x08monorail\x1a\x1bgoogle/protobuf/empty.proto\x1a\x1egoogle/protobuf/wrappers.proto\x1a\x1a\x61pi/api_proto/common.proto\x1a!api/api_proto/issue_objects.proto\"q\n\x12\x43reateIssueRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12\x14\n\x0cproject_name\x18\x02 \x01(\t\x12\x1e\n\x05issue\x18\x03 \x01(\x0b\x32\x0f.monorail.Issue\"_\n\x0fGetIssueRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12%\n\tissue_ref\x18\x02 \x01(\x0b\x32\x12.monorail.IssueRef\"/\n\rIssueResponse\x12\x1e\n\x05issue\x18\x01 \x01(\x0b\x32\x0f.monorail.Issue\"\xb4\x01\n\x12UpdateIssueRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12%\n\tissue_ref\x18\x02 \x01(\x0b\x32\x12.monorail.IssueRef\x12\x12\n\nsend_email\x18\x03 \x01(\x08\x12#\n\x05\x64\x65lta\x18\x04 \x01(\x0b\x32\x14.monorail.IssueDelta\x12\x17\n\x0f\x63omment_content\x18\x05 \x01(\t\"c\n\x13ListCommentsRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12%\n\tissue_ref\x18\x02 \x01(\x0b\x32\x12.monorail.IssueRef\";\n\x14ListCommentsResponse\x12#\n\x08\x63omments\x18\x01 \x03(\x0b\x32\x11.monorail.Comment\"\x8e\x01\n\x19\x44\x65leteIssueCommentRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12\x14\n\x0cproject_name\x18\x02 \x01(\t\x12\x10\n\x08local_id\x18\x03 \x01(\x03\x12\x12\n\ncomment_id\x18\x04 \x01(\x03\x12\x0e\n\x06\x64\x65lete\x18\x05 \x01(\x08\"\x9b\x06\n\nIssueDelta\x12,\n\x06status\x18\x01 \x01(\x0b\x32\x1c.google.protobuf.StringValue\x12$\n\towner_ref\x18\x02 \x01(\x0b\x32\x11.monorail.UserRef\x12&\n\x0b\x63\x63_refs_add\x18\x03 \x03(\x0b\x32\x11.monorail.UserRef\x12)\n\x0e\x63\x63_refs_remove\x18\x04 \x03(\x0b\x32\x11.monorail.UserRef\x12-\n\rcomp_refs_add\x18\x05 \x03(\x0b\x32\x16.monorail.ComponentRef\x12\x30\n\x10\x63omp_refs_remove\x18\x06 \x03(\x0b\x32\x16.monorail.ComponentRef\x12*\n\x0elabel_refs_add\x18\x07 \x03(\x0b\x32\x12.monorail.LabelRef\x12-\n\x11label_refs_remove\x18\x08 \x03(\x0b\x32\x12.monorail.LabelRef\x12,\n\x0e\x66ield_vals_add\x18\t \x03(\x0b\x32\x14.monorail.FieldValue\x12/\n\x11\x66ield_vals_remove\x18\n \x03(\x0b\x32\x14.monorail.FieldValue\x12(\n\x0c\x66ields_clear\x18\x0b \x03(\x0b\x32\x12.monorail.FieldRef\x12/\n\x13\x62locked_on_refs_add\x18\x0c \x03(\x0b\x32\x12.monorail.IssueRef\x12\x32\n\x16\x62locked_on_refs_remove\x18\r \x03(\x0b\x32\x12.monorail.IssueRef\x12.\n\x12\x62locking__refs_add\x18\x0e \x03(\x0b\x32\x12.monorail.IssueRef\x12\x30\n\x14\x62locking_refs_remove\x18\x0f \x03(\x0b\x32\x12.monorail.IssueRef\x12+\n\x0fmerged_into_ref\x18\x10 \x01(\x0b\x32\x12.monorail.IssueRef\x12-\n\x07summary\x18\x11 \x01(\x0b\x32\x1c.google.protobuf.StringValue\"\xea\x01\n\x15UpdateApprovalRequest\x12%\n\x05trace\x18\x01 \x01(\x0b\x32\x16.monorail.RequestTrace\x12%\n\tissue_ref\x18\x02 \x01(\x0b\x32\x12.monorail.IssueRef\x12%\n\tfield_ref\x18\x03 \x01(\x0b\x32\x12.monorail.FieldRef\x12/\n\x0e\x61pproval_delta\x18\x04 \x01(\x0b\x32\x17.monorail.ApprovalDelta\x12\x17\n\x0f\x63omment_content\x18\x05 \x01(\t\x12\x12\n\nsend_email\x18\x06 \x01(\x08\">\n\x16UpdateApprovalResponse\x12$\n\x08\x61pproval\x18\x01 \x01(\x0b\x32\x12.monorail.Approval2\xd7\x03\n\x06Issues\x12\x46\n\x0b\x43reateIssue\x12\x1c.monorail.CreateIssueRequest\x1a\x17.monorail.IssueResponse\"\x00\x12@\n\x08GetIssue\x12\x19.monorail.GetIssueRequest\x1a\x17.monorail.IssueResponse\"\x00\x12\x46\n\x0bUpdateIssue\x12\x1c.monorail.UpdateIssueRequest\x1a\x17.monorail.IssueResponse\"\x00\x12O\n\x0cListComments\x12\x1d.monorail.ListCommentsRequest\x1a\x1e.monorail.ListCommentsResponse\"\x00\x12S\n\x12\x44\x65leteIssueComment\x12#.monorail.DeleteIssueCommentRequest\x1a\x16.google.protobuf.Empty\"\x00\x12U\n\x0eUpdateApproval\x12\x1f.monorail.UpdateApprovalRequest\x1a .monorail.UpdateApprovalResponse\"\x00\x62\x06proto3')
  ,
  dependencies=[google_dot_protobuf_dot_empty__pb2.DESCRIPTOR,google_dot_protobuf_dot_wrappers__pb2.DESCRIPTOR,api_dot_api__proto_dot_common__pb2.DESCRIPTOR,api_dot_api__proto_dot_issue__objects__pb2.DESCRIPTOR,])
_sym_db.RegisterFileDescriptor(DESCRIPTOR)




_CREATEISSUEREQUEST = _descriptor.Descriptor(
  name='CreateIssueRequest',
  full_name='monorail.CreateIssueRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.CreateIssueRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='project_name', full_name='monorail.CreateIssueRequest.project_name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='issue', full_name='monorail.CreateIssueRequest.issue', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=164,
  serialized_end=277,
)


_GETISSUEREQUEST = _descriptor.Descriptor(
  name='GetIssueRequest',
  full_name='monorail.GetIssueRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.GetIssueRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='issue_ref', full_name='monorail.GetIssueRequest.issue_ref', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=279,
  serialized_end=374,
)


_ISSUERESPONSE = _descriptor.Descriptor(
  name='IssueResponse',
  full_name='monorail.IssueResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='issue', full_name='monorail.IssueResponse.issue', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=376,
  serialized_end=423,
)


_UPDATEISSUEREQUEST = _descriptor.Descriptor(
  name='UpdateIssueRequest',
  full_name='monorail.UpdateIssueRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.UpdateIssueRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='issue_ref', full_name='monorail.UpdateIssueRequest.issue_ref', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='send_email', full_name='monorail.UpdateIssueRequest.send_email', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='delta', full_name='monorail.UpdateIssueRequest.delta', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='comment_content', full_name='monorail.UpdateIssueRequest.comment_content', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=426,
  serialized_end=606,
)


_LISTCOMMENTSREQUEST = _descriptor.Descriptor(
  name='ListCommentsRequest',
  full_name='monorail.ListCommentsRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.ListCommentsRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='issue_ref', full_name='monorail.ListCommentsRequest.issue_ref', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=608,
  serialized_end=707,
)


_LISTCOMMENTSRESPONSE = _descriptor.Descriptor(
  name='ListCommentsResponse',
  full_name='monorail.ListCommentsResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='comments', full_name='monorail.ListCommentsResponse.comments', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=709,
  serialized_end=768,
)


_DELETEISSUECOMMENTREQUEST = _descriptor.Descriptor(
  name='DeleteIssueCommentRequest',
  full_name='monorail.DeleteIssueCommentRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.DeleteIssueCommentRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='project_name', full_name='monorail.DeleteIssueCommentRequest.project_name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='local_id', full_name='monorail.DeleteIssueCommentRequest.local_id', index=2,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='comment_id', full_name='monorail.DeleteIssueCommentRequest.comment_id', index=3,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='delete', full_name='monorail.DeleteIssueCommentRequest.delete', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=771,
  serialized_end=913,
)


_ISSUEDELTA = _descriptor.Descriptor(
  name='IssueDelta',
  full_name='monorail.IssueDelta',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='status', full_name='monorail.IssueDelta.status', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='owner_ref', full_name='monorail.IssueDelta.owner_ref', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='cc_refs_add', full_name='monorail.IssueDelta.cc_refs_add', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='cc_refs_remove', full_name='monorail.IssueDelta.cc_refs_remove', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='comp_refs_add', full_name='monorail.IssueDelta.comp_refs_add', index=4,
      number=5, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='comp_refs_remove', full_name='monorail.IssueDelta.comp_refs_remove', index=5,
      number=6, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='label_refs_add', full_name='monorail.IssueDelta.label_refs_add', index=6,
      number=7, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='label_refs_remove', full_name='monorail.IssueDelta.label_refs_remove', index=7,
      number=8, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='field_vals_add', full_name='monorail.IssueDelta.field_vals_add', index=8,
      number=9, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='field_vals_remove', full_name='monorail.IssueDelta.field_vals_remove', index=9,
      number=10, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='fields_clear', full_name='monorail.IssueDelta.fields_clear', index=10,
      number=11, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='blocked_on_refs_add', full_name='monorail.IssueDelta.blocked_on_refs_add', index=11,
      number=12, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='blocked_on_refs_remove', full_name='monorail.IssueDelta.blocked_on_refs_remove', index=12,
      number=13, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='blocking__refs_add', full_name='monorail.IssueDelta.blocking__refs_add', index=13,
      number=14, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='blocking_refs_remove', full_name='monorail.IssueDelta.blocking_refs_remove', index=14,
      number=15, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='merged_into_ref', full_name='monorail.IssueDelta.merged_into_ref', index=15,
      number=16, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='summary', full_name='monorail.IssueDelta.summary', index=16,
      number=17, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=916,
  serialized_end=1711,
)


_UPDATEAPPROVALREQUEST = _descriptor.Descriptor(
  name='UpdateApprovalRequest',
  full_name='monorail.UpdateApprovalRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='trace', full_name='monorail.UpdateApprovalRequest.trace', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='issue_ref', full_name='monorail.UpdateApprovalRequest.issue_ref', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='field_ref', full_name='monorail.UpdateApprovalRequest.field_ref', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='approval_delta', full_name='monorail.UpdateApprovalRequest.approval_delta', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='comment_content', full_name='monorail.UpdateApprovalRequest.comment_content', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='send_email', full_name='monorail.UpdateApprovalRequest.send_email', index=5,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1714,
  serialized_end=1948,
)


_UPDATEAPPROVALRESPONSE = _descriptor.Descriptor(
  name='UpdateApprovalResponse',
  full_name='monorail.UpdateApprovalResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='approval', full_name='monorail.UpdateApprovalResponse.approval', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1950,
  serialized_end=2012,
)

_CREATEISSUEREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_CREATEISSUEREQUEST.fields_by_name['issue'].message_type = api_dot_api__proto_dot_issue__objects__pb2._ISSUE
_GETISSUEREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_GETISSUEREQUEST.fields_by_name['issue_ref'].message_type = api_dot_api__proto_dot_common__pb2._ISSUEREF
_ISSUERESPONSE.fields_by_name['issue'].message_type = api_dot_api__proto_dot_issue__objects__pb2._ISSUE
_UPDATEISSUEREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_UPDATEISSUEREQUEST.fields_by_name['issue_ref'].message_type = api_dot_api__proto_dot_common__pb2._ISSUEREF
_UPDATEISSUEREQUEST.fields_by_name['delta'].message_type = _ISSUEDELTA
_LISTCOMMENTSREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_LISTCOMMENTSREQUEST.fields_by_name['issue_ref'].message_type = api_dot_api__proto_dot_common__pb2._ISSUEREF
_LISTCOMMENTSRESPONSE.fields_by_name['comments'].message_type = api_dot_api__proto_dot_issue__objects__pb2._COMMENT
_DELETEISSUECOMMENTREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_ISSUEDELTA.fields_by_name['status'].message_type = google_dot_protobuf_dot_wrappers__pb2._STRINGVALUE
_ISSUEDELTA.fields_by_name['owner_ref'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_ISSUEDELTA.fields_by_name['cc_refs_add'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_ISSUEDELTA.fields_by_name['cc_refs_remove'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_ISSUEDELTA.fields_by_name['comp_refs_add'].message_type = api_dot_api__proto_dot_common__pb2._COMPONENTREF
_ISSUEDELTA.fields_by_name['comp_refs_remove'].message_type = api_dot_api__proto_dot_common__pb2._COMPONENTREF
_ISSUEDELTA.fields_by_name['label_refs_add'].message_type = api_dot_api__proto_dot_common__pb2._LABELREF
_ISSUEDELTA.fields_by_name['label_refs_remove'].message_type = api_dot_api__proto_dot_common__pb2._LABELREF
_ISSUEDELTA.fields_by_name['field_vals_add'].message_type = api_dot_api__proto_dot_issue__objects__pb2._FIELDVALUE
_ISSUEDELTA.fields_by_name['field_vals_remove'].message_type = api_dot_api__proto_dot_issue__objects__pb2._FIELDVALUE
_ISSUEDELTA.fields_by_name['fields_clear'].message_type = api_dot_api__proto_dot_common__pb2._FIELDREF
_ISSUEDELTA.fields_by_name['blocked_on_refs_add'].message_type = api_dot_api__proto_dot_common__pb2._ISSUEREF
_ISSUEDELTA.fields_by_name['blocked_on_refs_remove'].message_type = api_dot_api__proto_dot_common__pb2._ISSUEREF
_ISSUEDELTA.fields_by_name['blocking__refs_add'].message_type = api_dot_api__proto_dot_common__pb2._ISSUEREF
_ISSUEDELTA.fields_by_name['blocking_refs_remove'].message_type = api_dot_api__proto_dot_common__pb2._ISSUEREF
_ISSUEDELTA.fields_by_name['merged_into_ref'].message_type = api_dot_api__proto_dot_common__pb2._ISSUEREF
_ISSUEDELTA.fields_by_name['summary'].message_type = google_dot_protobuf_dot_wrappers__pb2._STRINGVALUE
_UPDATEAPPROVALREQUEST.fields_by_name['trace'].message_type = api_dot_api__proto_dot_common__pb2._REQUESTTRACE
_UPDATEAPPROVALREQUEST.fields_by_name['issue_ref'].message_type = api_dot_api__proto_dot_common__pb2._ISSUEREF
_UPDATEAPPROVALREQUEST.fields_by_name['field_ref'].message_type = api_dot_api__proto_dot_common__pb2._FIELDREF
_UPDATEAPPROVALREQUEST.fields_by_name['approval_delta'].message_type = api_dot_api__proto_dot_issue__objects__pb2._APPROVALDELTA
_UPDATEAPPROVALRESPONSE.fields_by_name['approval'].message_type = api_dot_api__proto_dot_issue__objects__pb2._APPROVAL
DESCRIPTOR.message_types_by_name['CreateIssueRequest'] = _CREATEISSUEREQUEST
DESCRIPTOR.message_types_by_name['GetIssueRequest'] = _GETISSUEREQUEST
DESCRIPTOR.message_types_by_name['IssueResponse'] = _ISSUERESPONSE
DESCRIPTOR.message_types_by_name['UpdateIssueRequest'] = _UPDATEISSUEREQUEST
DESCRIPTOR.message_types_by_name['ListCommentsRequest'] = _LISTCOMMENTSREQUEST
DESCRIPTOR.message_types_by_name['ListCommentsResponse'] = _LISTCOMMENTSRESPONSE
DESCRIPTOR.message_types_by_name['DeleteIssueCommentRequest'] = _DELETEISSUECOMMENTREQUEST
DESCRIPTOR.message_types_by_name['IssueDelta'] = _ISSUEDELTA
DESCRIPTOR.message_types_by_name['UpdateApprovalRequest'] = _UPDATEAPPROVALREQUEST
DESCRIPTOR.message_types_by_name['UpdateApprovalResponse'] = _UPDATEAPPROVALRESPONSE

CreateIssueRequest = _reflection.GeneratedProtocolMessageType('CreateIssueRequest', (_message.Message,), dict(
  DESCRIPTOR = _CREATEISSUEREQUEST,
  __module__ = 'api.api_proto.issues_pb2'
  # @@protoc_insertion_point(class_scope:monorail.CreateIssueRequest)
  ))
_sym_db.RegisterMessage(CreateIssueRequest)

GetIssueRequest = _reflection.GeneratedProtocolMessageType('GetIssueRequest', (_message.Message,), dict(
  DESCRIPTOR = _GETISSUEREQUEST,
  __module__ = 'api.api_proto.issues_pb2'
  # @@protoc_insertion_point(class_scope:monorail.GetIssueRequest)
  ))
_sym_db.RegisterMessage(GetIssueRequest)

IssueResponse = _reflection.GeneratedProtocolMessageType('IssueResponse', (_message.Message,), dict(
  DESCRIPTOR = _ISSUERESPONSE,
  __module__ = 'api.api_proto.issues_pb2'
  # @@protoc_insertion_point(class_scope:monorail.IssueResponse)
  ))
_sym_db.RegisterMessage(IssueResponse)

UpdateIssueRequest = _reflection.GeneratedProtocolMessageType('UpdateIssueRequest', (_message.Message,), dict(
  DESCRIPTOR = _UPDATEISSUEREQUEST,
  __module__ = 'api.api_proto.issues_pb2'
  # @@protoc_insertion_point(class_scope:monorail.UpdateIssueRequest)
  ))
_sym_db.RegisterMessage(UpdateIssueRequest)

ListCommentsRequest = _reflection.GeneratedProtocolMessageType('ListCommentsRequest', (_message.Message,), dict(
  DESCRIPTOR = _LISTCOMMENTSREQUEST,
  __module__ = 'api.api_proto.issues_pb2'
  # @@protoc_insertion_point(class_scope:monorail.ListCommentsRequest)
  ))
_sym_db.RegisterMessage(ListCommentsRequest)

ListCommentsResponse = _reflection.GeneratedProtocolMessageType('ListCommentsResponse', (_message.Message,), dict(
  DESCRIPTOR = _LISTCOMMENTSRESPONSE,
  __module__ = 'api.api_proto.issues_pb2'
  # @@protoc_insertion_point(class_scope:monorail.ListCommentsResponse)
  ))
_sym_db.RegisterMessage(ListCommentsResponse)

DeleteIssueCommentRequest = _reflection.GeneratedProtocolMessageType('DeleteIssueCommentRequest', (_message.Message,), dict(
  DESCRIPTOR = _DELETEISSUECOMMENTREQUEST,
  __module__ = 'api.api_proto.issues_pb2'
  # @@protoc_insertion_point(class_scope:monorail.DeleteIssueCommentRequest)
  ))
_sym_db.RegisterMessage(DeleteIssueCommentRequest)

IssueDelta = _reflection.GeneratedProtocolMessageType('IssueDelta', (_message.Message,), dict(
  DESCRIPTOR = _ISSUEDELTA,
  __module__ = 'api.api_proto.issues_pb2'
  # @@protoc_insertion_point(class_scope:monorail.IssueDelta)
  ))
_sym_db.RegisterMessage(IssueDelta)

UpdateApprovalRequest = _reflection.GeneratedProtocolMessageType('UpdateApprovalRequest', (_message.Message,), dict(
  DESCRIPTOR = _UPDATEAPPROVALREQUEST,
  __module__ = 'api.api_proto.issues_pb2'
  # @@protoc_insertion_point(class_scope:monorail.UpdateApprovalRequest)
  ))
_sym_db.RegisterMessage(UpdateApprovalRequest)

UpdateApprovalResponse = _reflection.GeneratedProtocolMessageType('UpdateApprovalResponse', (_message.Message,), dict(
  DESCRIPTOR = _UPDATEAPPROVALRESPONSE,
  __module__ = 'api.api_proto.issues_pb2'
  # @@protoc_insertion_point(class_scope:monorail.UpdateApprovalResponse)
  ))
_sym_db.RegisterMessage(UpdateApprovalResponse)


# @@protoc_insertion_point(module_scope)
