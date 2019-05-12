// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/appengine/arquebus/app/config/config.proto

package config

import (
	fmt "fmt"
	proto "github.com/golang/protobuf/proto"
	duration "github.com/golang/protobuf/ptypes/duration"
	math "math"
)

// Reference imports to suppress errors if they are not otherwise used.
var _ = proto.Marshal
var _ = fmt.Errorf
var _ = math.Inf

// This is a compile-time assertion to ensure that this generated file
// is compatible with the proto package it is being compiled against.
// A compilation error at this line likely means your copy of the
// proto package needs to be updated.
const _ = proto.ProtoPackageIsVersion3 // please upgrade the proto package

type Oncall_Position int32

const (
	Oncall_UNSET     Oncall_Position = 0
	Oncall_PRIMARY   Oncall_Position = 1
	Oncall_SECONDARY Oncall_Position = 2
)

var Oncall_Position_name = map[int32]string{
	0: "UNSET",
	1: "PRIMARY",
	2: "SECONDARY",
}

var Oncall_Position_value = map[string]int32{
	"UNSET":     0,
	"PRIMARY":   1,
	"SECONDARY": 2,
}

func (x Oncall_Position) String() string {
	return proto.EnumName(Oncall_Position_name, int32(x))
}

func (Oncall_Position) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_421d741a02045ab0, []int{2, 0}
}

// Config is the service-wide configuration data for Arquebus
type Config struct {
	// AccessGroup is the luci-auth group who has access to admin pages and
	// APIs.
	AccessGroup string `protobuf:"bytes,1,opt,name=access_group,json=accessGroup,proto3" json:"access_group,omitempty"`
	// The endpoint for Monorail APIs.
	MonorailHostname string `protobuf:"bytes,2,opt,name=monorail_hostname,json=monorailHostname,proto3" json:"monorail_hostname,omitempty"`
	// A list of Assigner config(s).
	Assigners []*Assigner `protobuf:"bytes,3,rep,name=assigners,proto3" json:"assigners,omitempty"`
	// The endpoint for RotaNG APIs.
	RotangHostname       string   `protobuf:"bytes,4,opt,name=rotang_hostname,json=rotangHostname,proto3" json:"rotang_hostname,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Config) Reset()         { *m = Config{} }
func (m *Config) String() string { return proto.CompactTextString(m) }
func (*Config) ProtoMessage()    {}
func (*Config) Descriptor() ([]byte, []int) {
	return fileDescriptor_421d741a02045ab0, []int{0}
}

func (m *Config) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Config.Unmarshal(m, b)
}
func (m *Config) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Config.Marshal(b, m, deterministic)
}
func (m *Config) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Config.Merge(m, src)
}
func (m *Config) XXX_Size() int {
	return xxx_messageInfo_Config.Size(m)
}
func (m *Config) XXX_DiscardUnknown() {
	xxx_messageInfo_Config.DiscardUnknown(m)
}

var xxx_messageInfo_Config proto.InternalMessageInfo

func (m *Config) GetAccessGroup() string {
	if m != nil {
		return m.AccessGroup
	}
	return ""
}

func (m *Config) GetMonorailHostname() string {
	if m != nil {
		return m.MonorailHostname
	}
	return ""
}

func (m *Config) GetAssigners() []*Assigner {
	if m != nil {
		return m.Assigners
	}
	return nil
}

func (m *Config) GetRotangHostname() string {
	if m != nil {
		return m.RotangHostname
	}
	return ""
}

// IssueQuery describes the issue query to be used for searching unassigned
// issues in Monorail.
type IssueQuery struct {
	// Free-form text query.
	Q string `protobuf:"bytes,1,opt,name=q,proto3" json:"q,omitempty"`
	// String name of the projects to search issues for, e.g. "chromium".
	ProjectNames         []string `protobuf:"bytes,2,rep,name=project_names,json=projectNames,proto3" json:"project_names,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *IssueQuery) Reset()         { *m = IssueQuery{} }
func (m *IssueQuery) String() string { return proto.CompactTextString(m) }
func (*IssueQuery) ProtoMessage()    {}
func (*IssueQuery) Descriptor() ([]byte, []int) {
	return fileDescriptor_421d741a02045ab0, []int{1}
}

func (m *IssueQuery) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_IssueQuery.Unmarshal(m, b)
}
func (m *IssueQuery) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_IssueQuery.Marshal(b, m, deterministic)
}
func (m *IssueQuery) XXX_Merge(src proto.Message) {
	xxx_messageInfo_IssueQuery.Merge(m, src)
}
func (m *IssueQuery) XXX_Size() int {
	return xxx_messageInfo_IssueQuery.Size(m)
}
func (m *IssueQuery) XXX_DiscardUnknown() {
	xxx_messageInfo_IssueQuery.DiscardUnknown(m)
}

var xxx_messageInfo_IssueQuery proto.InternalMessageInfo

func (m *IssueQuery) GetQ() string {
	if m != nil {
		return m.Q
	}
	return ""
}

func (m *IssueQuery) GetProjectNames() []string {
	if m != nil {
		return m.ProjectNames
	}
	return nil
}

// Oncall represents a rotation shift modelled in RotaNG.
type Oncall struct {
	// The name of a rotation.
	Rotation string `protobuf:"bytes,1,opt,name=rotation,proto3" json:"rotation,omitempty"`
	// The oncall position in the shift.
	Position             Oncall_Position `protobuf:"varint,2,opt,name=position,proto3,enum=arquebus.config.Oncall_Position" json:"position,omitempty"`
	XXX_NoUnkeyedLiteral struct{}        `json:"-"`
	XXX_unrecognized     []byte          `json:"-"`
	XXX_sizecache        int32           `json:"-"`
}

func (m *Oncall) Reset()         { *m = Oncall{} }
func (m *Oncall) String() string { return proto.CompactTextString(m) }
func (*Oncall) ProtoMessage()    {}
func (*Oncall) Descriptor() ([]byte, []int) {
	return fileDescriptor_421d741a02045ab0, []int{2}
}

func (m *Oncall) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Oncall.Unmarshal(m, b)
}
func (m *Oncall) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Oncall.Marshal(b, m, deterministic)
}
func (m *Oncall) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Oncall.Merge(m, src)
}
func (m *Oncall) XXX_Size() int {
	return xxx_messageInfo_Oncall.Size(m)
}
func (m *Oncall) XXX_DiscardUnknown() {
	xxx_messageInfo_Oncall.DiscardUnknown(m)
}

var xxx_messageInfo_Oncall proto.InternalMessageInfo

func (m *Oncall) GetRotation() string {
	if m != nil {
		return m.Rotation
	}
	return ""
}

func (m *Oncall) GetPosition() Oncall_Position {
	if m != nil {
		return m.Position
	}
	return Oncall_UNSET
}

// UserSource represents a single source to find a valid Monorail user to whom
// Arquebus will assign or cc issues found.
type UserSource struct {
	// Types that are valid to be assigned to From:
	//	*UserSource_Oncall
	//	*UserSource_Email
	From                 isUserSource_From `protobuf_oneof:"from"`
	XXX_NoUnkeyedLiteral struct{}          `json:"-"`
	XXX_unrecognized     []byte            `json:"-"`
	XXX_sizecache        int32             `json:"-"`
}

func (m *UserSource) Reset()         { *m = UserSource{} }
func (m *UserSource) String() string { return proto.CompactTextString(m) }
func (*UserSource) ProtoMessage()    {}
func (*UserSource) Descriptor() ([]byte, []int) {
	return fileDescriptor_421d741a02045ab0, []int{3}
}

func (m *UserSource) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_UserSource.Unmarshal(m, b)
}
func (m *UserSource) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_UserSource.Marshal(b, m, deterministic)
}
func (m *UserSource) XXX_Merge(src proto.Message) {
	xxx_messageInfo_UserSource.Merge(m, src)
}
func (m *UserSource) XXX_Size() int {
	return xxx_messageInfo_UserSource.Size(m)
}
func (m *UserSource) XXX_DiscardUnknown() {
	xxx_messageInfo_UserSource.DiscardUnknown(m)
}

var xxx_messageInfo_UserSource proto.InternalMessageInfo

type isUserSource_From interface {
	isUserSource_From()
}

type UserSource_Oncall struct {
	Oncall *Oncall `protobuf:"bytes,1,opt,name=oncall,proto3,oneof"`
}

type UserSource_Email struct {
	Email string `protobuf:"bytes,2,opt,name=email,proto3,oneof"`
}

func (*UserSource_Oncall) isUserSource_From() {}

func (*UserSource_Email) isUserSource_From() {}

func (m *UserSource) GetFrom() isUserSource_From {
	if m != nil {
		return m.From
	}
	return nil
}

func (m *UserSource) GetOncall() *Oncall {
	if x, ok := m.GetFrom().(*UserSource_Oncall); ok {
		return x.Oncall
	}
	return nil
}

func (m *UserSource) GetEmail() string {
	if x, ok := m.GetFrom().(*UserSource_Email); ok {
		return x.Email
	}
	return ""
}

// XXX_OneofWrappers is for the internal use of the proto package.
func (*UserSource) XXX_OneofWrappers() []interface{} {
	return []interface{}{
		(*UserSource_Oncall)(nil),
		(*UserSource_Email)(nil),
	}
}

// Assigner contains specifications for an Assigner job.
type Assigner struct {
	// The unique ID of the Assigner.
	//
	// This value will be used in URLs of UI, so keep it short. Note that
	// only lowercase alphabet letters and numbers are allowed. A hyphen may
	// be placed between letters and numbers.
	Id string `protobuf:"bytes,1,opt,name=id,proto3" json:"id,omitempty"`
	// An email list of the owners of the Assigner.
	Owners []string `protobuf:"bytes,2,rep,name=owners,proto3" json:"owners,omitempty"`
	// The duration between the start of an Assigner run and the next one.
	//
	// This value be at least a minute long.
	Interval *duration.Duration `protobuf:"bytes,3,opt,name=interval,proto3" json:"interval,omitempty"`
	// IssueQuery describes the search criteria to look for issues to assign.
	IssueQuery *IssueQuery `protobuf:"bytes,4,opt,name=issue_query,json=issueQuery,proto3" json:"issue_query,omitempty"`
	// If multiple values are specified in assignees, Arquebus iterates the list
	// in the order until it finds a currently available assignee. Note that
	// Monorail users are always assumed to be available.
	Assignees []*UserSource `protobuf:"bytes,6,rep,name=assignees,proto3" json:"assignees,omitempty"`
	// If multiple values are specified in ccs, all the available roations and
	// users are added to the CC of searched issues.
	Ccs []*UserSource `protobuf:"bytes,7,rep,name=ccs,proto3" json:"ccs,omitempty"`
	// If DryRun is set, Assigner doesn't update the found issues.
	DryRun bool `protobuf:"varint,8,opt,name=dry_run,json=dryRun,proto3" json:"dry_run,omitempty"`
	// The description shown on UI.
	Description          string   `protobuf:"bytes,9,opt,name=description,proto3" json:"description,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Assigner) Reset()         { *m = Assigner{} }
func (m *Assigner) String() string { return proto.CompactTextString(m) }
func (*Assigner) ProtoMessage()    {}
func (*Assigner) Descriptor() ([]byte, []int) {
	return fileDescriptor_421d741a02045ab0, []int{4}
}

func (m *Assigner) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Assigner.Unmarshal(m, b)
}
func (m *Assigner) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Assigner.Marshal(b, m, deterministic)
}
func (m *Assigner) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Assigner.Merge(m, src)
}
func (m *Assigner) XXX_Size() int {
	return xxx_messageInfo_Assigner.Size(m)
}
func (m *Assigner) XXX_DiscardUnknown() {
	xxx_messageInfo_Assigner.DiscardUnknown(m)
}

var xxx_messageInfo_Assigner proto.InternalMessageInfo

func (m *Assigner) GetId() string {
	if m != nil {
		return m.Id
	}
	return ""
}

func (m *Assigner) GetOwners() []string {
	if m != nil {
		return m.Owners
	}
	return nil
}

func (m *Assigner) GetInterval() *duration.Duration {
	if m != nil {
		return m.Interval
	}
	return nil
}

func (m *Assigner) GetIssueQuery() *IssueQuery {
	if m != nil {
		return m.IssueQuery
	}
	return nil
}

func (m *Assigner) GetAssignees() []*UserSource {
	if m != nil {
		return m.Assignees
	}
	return nil
}

func (m *Assigner) GetCcs() []*UserSource {
	if m != nil {
		return m.Ccs
	}
	return nil
}

func (m *Assigner) GetDryRun() bool {
	if m != nil {
		return m.DryRun
	}
	return false
}

func (m *Assigner) GetDescription() string {
	if m != nil {
		return m.Description
	}
	return ""
}

func init() {
	proto.RegisterEnum("arquebus.config.Oncall_Position", Oncall_Position_name, Oncall_Position_value)
	proto.RegisterType((*Config)(nil), "arquebus.config.Config")
	proto.RegisterType((*IssueQuery)(nil), "arquebus.config.IssueQuery")
	proto.RegisterType((*Oncall)(nil), "arquebus.config.Oncall")
	proto.RegisterType((*UserSource)(nil), "arquebus.config.UserSource")
	proto.RegisterType((*Assigner)(nil), "arquebus.config.Assigner")
}

func init() {
	proto.RegisterFile("infra/appengine/arquebus/app/config/config.proto", fileDescriptor_421d741a02045ab0)
}

var fileDescriptor_421d741a02045ab0 = []byte{
	// 542 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x84, 0x53, 0xcb, 0x6e, 0xd3, 0x40,
	0x14, 0xad, 0x9d, 0xd6, 0xb5, 0xaf, 0xfb, 0x62, 0x16, 0xad, 0x5b, 0x24, 0x64, 0xcc, 0x82, 0x48,
	0x08, 0x87, 0x06, 0x21, 0x84, 0x54, 0x09, 0xf5, 0x25, 0xd2, 0x05, 0x69, 0x99, 0xd0, 0x05, 0x6c,
	0xac, 0x89, 0x3d, 0x31, 0x83, 0x9c, 0x19, 0x67, 0xc6, 0x06, 0xe5, 0x43, 0xf8, 0x19, 0xbe, 0x81,
	0x8f, 0x42, 0x1e, 0xdb, 0x31, 0x22, 0x42, 0xac, 0xac, 0x7b, 0xe6, 0xdc, 0xe7, 0x39, 0x86, 0x17,
	0x8c, 0xcf, 0x24, 0x19, 0x90, 0x3c, 0xa7, 0x3c, 0x65, 0x9c, 0x0e, 0x88, 0x5c, 0x94, 0x74, 0x5a,
	0xaa, 0x0a, 0x1a, 0xc4, 0x82, 0xcf, 0x58, 0xda, 0x7c, 0xc2, 0x5c, 0x8a, 0x42, 0xa0, 0xfd, 0x96,
	0x11, 0xd6, 0xf0, 0xc9, 0xa3, 0x54, 0x88, 0x34, 0xa3, 0x03, 0xfd, 0x3c, 0x2d, 0x67, 0x83, 0xa4,
	0x94, 0xa4, 0x60, 0x82, 0xd7, 0x09, 0xc1, 0x4f, 0x03, 0xac, 0x4b, 0x4d, 0x45, 0x8f, 0x61, 0x87,
	0xc4, 0x31, 0x55, 0x2a, 0x4a, 0xa5, 0x28, 0x73, 0xcf, 0xf0, 0x8d, 0xbe, 0x83, 0xdd, 0x1a, 0x7b,
	0x57, 0x41, 0xe8, 0x19, 0x3c, 0x98, 0x0b, 0x2e, 0x24, 0x61, 0x59, 0xf4, 0x45, 0xa8, 0x82, 0x93,
	0x39, 0xf5, 0x4c, 0xcd, 0x3b, 0x68, 0x1f, 0x46, 0x0d, 0x8e, 0x5e, 0x83, 0x43, 0x94, 0x62, 0x29,
	0xa7, 0x52, 0x79, 0x3d, 0xbf, 0xd7, 0x77, 0x87, 0xc7, 0xe1, 0x5f, 0xf3, 0x85, 0xe7, 0x0d, 0x03,
	0x77, 0x5c, 0xf4, 0x14, 0xf6, 0xa5, 0x28, 0x08, 0x4f, 0xbb, 0x1e, 0x9b, 0xba, 0xc7, 0x5e, 0x0d,
	0xb7, 0x1d, 0x82, 0xb7, 0x00, 0x37, 0x4a, 0x95, 0xf4, 0x43, 0x49, 0xe5, 0x12, 0xed, 0x80, 0xb1,
	0x68, 0x86, 0x36, 0x16, 0xe8, 0x09, 0xec, 0xe6, 0x52, 0x7c, 0xa5, 0x71, 0x11, 0x55, 0x5c, 0xe5,
	0x99, 0x7e, 0xaf, 0xef, 0xe0, 0x9d, 0x06, 0x1c, 0x57, 0x58, 0xf0, 0xc3, 0x00, 0xeb, 0x96, 0xc7,
	0x24, 0xcb, 0xd0, 0x09, 0xd8, 0x55, 0xf5, 0xea, 0x34, 0x4d, 0x91, 0x55, 0x8c, 0xce, 0xc0, 0xce,
	0x85, 0x62, 0xfa, 0xad, 0xda, 0x76, 0x6f, 0xe8, 0xaf, 0x2d, 0x52, 0x97, 0x09, 0xef, 0x1a, 0x1e,
	0x5e, 0x65, 0x04, 0xa7, 0x60, 0xb7, 0x28, 0x72, 0x60, 0xeb, 0x7e, 0x3c, 0xb9, 0xfe, 0x78, 0xb0,
	0x81, 0x5c, 0xd8, 0xbe, 0xc3, 0x37, 0xef, 0xcf, 0xf1, 0xa7, 0x03, 0x03, 0xed, 0x82, 0x33, 0xb9,
	0xbe, 0xbc, 0x1d, 0x5f, 0x55, 0xa1, 0x19, 0x44, 0x00, 0xf7, 0x8a, 0xca, 0x89, 0x28, 0x65, 0x4c,
	0xd1, 0x29, 0x58, 0x42, 0x57, 0xd7, 0x83, 0xb9, 0xc3, 0xa3, 0x7f, 0x34, 0x1f, 0x6d, 0xe0, 0x86,
	0x88, 0x0e, 0x61, 0x8b, 0xce, 0x09, 0xcb, 0x6a, 0x71, 0x46, 0x1b, 0xb8, 0x0e, 0x2f, 0x2c, 0xd8,
	0x9c, 0x49, 0x31, 0x0f, 0x7e, 0x99, 0x60, 0xb7, 0xa7, 0x47, 0x7b, 0x60, 0xb2, 0xa4, 0x59, 0xda,
	0x64, 0x09, 0x3a, 0x04, 0x4b, 0x7c, 0xd7, 0xaa, 0xd5, 0x37, 0x6b, 0x22, 0xf4, 0x0a, 0x6c, 0xc6,
	0x0b, 0x2a, 0xbf, 0x91, 0xcc, 0xeb, 0xe9, 0x49, 0x8e, 0xc3, 0xda, 0x5e, 0x61, 0x6b, 0xaf, 0xf0,
	0xaa, 0xb1, 0x17, 0x5e, 0x51, 0xd1, 0x19, 0xb8, 0xac, 0x52, 0x29, 0x5a, 0x54, 0x32, 0x69, 0x29,
	0xdd, 0xe1, 0xc3, 0xb5, 0x1d, 0x3a, 0x25, 0x31, 0xb0, 0x4e, 0xd5, 0x37, 0x2b, 0x17, 0x51, 0xe5,
	0x59, 0xda, 0x45, 0xeb, 0xb9, 0xdd, 0xb1, 0x70, 0xc7, 0x46, 0xcf, 0xa1, 0x17, 0xc7, 0xca, 0xdb,
	0xfe, 0x7f, 0x52, 0xc5, 0x43, 0x47, 0xb0, 0x9d, 0xc8, 0x65, 0x24, 0x4b, 0xee, 0xd9, 0xbe, 0xd1,
	0xb7, 0xb1, 0x95, 0xc8, 0x25, 0x2e, 0x39, 0xf2, 0xc1, 0x4d, 0xa8, 0x8a, 0x25, 0xcb, 0xb5, 0x03,
	0x9c, 0xfa, 0xbf, 0xf8, 0x03, 0xba, 0xb0, 0x3f, 0x5b, 0x75, 0xd1, 0xa9, 0xa5, 0x2f, 0xf1, 0xf2,
	0x77, 0x00, 0x00, 0x00, 0xff, 0xff, 0x44, 0xac, 0x21, 0x34, 0xbb, 0x03, 0x00, 0x00,
}
