// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/appengine/crosskylabadmin/api/fleet/v1/common.proto

package fleet

import (
	fmt "fmt"
	proto "github.com/golang/protobuf/proto"
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
const _ = proto.ProtoPackageIsVersion2 // please upgrade the proto package

// BotSelector is used in various fleet RPCs to filter the Swarming bots that
// the RPC applies to.
//
// For example, it is used to select the bots to summarize by the Tracker RPCs,
// and to select the bots against which admin tasks are managed by the Tasker
// RPCs.
type BotSelector struct {
	// dut_id selects a bot by the dut_id dimension.
	DutId string `protobuf:"bytes,1,opt,name=dut_id,json=dutId,proto3" json:"dut_id,omitempty"`
	// dimensions select bots by Swarming dimensions.
	//
	// All fields in the dimension message must match for a bot to be selected.
	Dimensions           *BotDimensions `protobuf:"bytes,2,opt,name=dimensions,proto3" json:"dimensions,omitempty"`
	XXX_NoUnkeyedLiteral struct{}       `json:"-"`
	XXX_unrecognized     []byte         `json:"-"`
	XXX_sizecache        int32          `json:"-"`
}

func (m *BotSelector) Reset()         { *m = BotSelector{} }
func (m *BotSelector) String() string { return proto.CompactTextString(m) }
func (*BotSelector) ProtoMessage()    {}
func (*BotSelector) Descriptor() ([]byte, []int) {
	return fileDescriptor_e1fa3f8860ba148c, []int{0}
}

func (m *BotSelector) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_BotSelector.Unmarshal(m, b)
}
func (m *BotSelector) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_BotSelector.Marshal(b, m, deterministic)
}
func (m *BotSelector) XXX_Merge(src proto.Message) {
	xxx_messageInfo_BotSelector.Merge(m, src)
}
func (m *BotSelector) XXX_Size() int {
	return xxx_messageInfo_BotSelector.Size(m)
}
func (m *BotSelector) XXX_DiscardUnknown() {
	xxx_messageInfo_BotSelector.DiscardUnknown(m)
}

var xxx_messageInfo_BotSelector proto.InternalMessageInfo

func (m *BotSelector) GetDutId() string {
	if m != nil {
		return m.DutId
	}
	return ""
}

func (m *BotSelector) GetDimensions() *BotDimensions {
	if m != nil {
		return m.Dimensions
	}
	return nil
}

// BotDimensions is a subset of Swarming bot dimensions.
type BotDimensions struct {
	Pools                []string `protobuf:"bytes,1,rep,name=pools,proto3" json:"pools,omitempty"`
	Model                string   `protobuf:"bytes,2,opt,name=model,proto3" json:"model,omitempty"`
	DutName              string   `protobuf:"bytes,3,opt,name=dut_name,json=dutName,proto3" json:"dut_name,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *BotDimensions) Reset()         { *m = BotDimensions{} }
func (m *BotDimensions) String() string { return proto.CompactTextString(m) }
func (*BotDimensions) ProtoMessage()    {}
func (*BotDimensions) Descriptor() ([]byte, []int) {
	return fileDescriptor_e1fa3f8860ba148c, []int{1}
}

func (m *BotDimensions) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_BotDimensions.Unmarshal(m, b)
}
func (m *BotDimensions) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_BotDimensions.Marshal(b, m, deterministic)
}
func (m *BotDimensions) XXX_Merge(src proto.Message) {
	xxx_messageInfo_BotDimensions.Merge(m, src)
}
func (m *BotDimensions) XXX_Size() int {
	return xxx_messageInfo_BotDimensions.Size(m)
}
func (m *BotDimensions) XXX_DiscardUnknown() {
	xxx_messageInfo_BotDimensions.DiscardUnknown(m)
}

var xxx_messageInfo_BotDimensions proto.InternalMessageInfo

func (m *BotDimensions) GetPools() []string {
	if m != nil {
		return m.Pools
	}
	return nil
}

func (m *BotDimensions) GetModel() string {
	if m != nil {
		return m.Model
	}
	return ""
}

func (m *BotDimensions) GetDutName() string {
	if m != nil {
		return m.DutName
	}
	return ""
}

func init() {
	proto.RegisterType((*BotSelector)(nil), "crosskylabadmin.fleet.BotSelector")
	proto.RegisterType((*BotDimensions)(nil), "crosskylabadmin.fleet.BotDimensions")
}

func init() {
	proto.RegisterFile("infra/appengine/crosskylabadmin/api/fleet/v1/common.proto", fileDescriptor_e1fa3f8860ba148c)
}

var fileDescriptor_e1fa3f8860ba148c = []byte{
	// 226 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x6c, 0x8f, 0x31, 0x4b, 0xc4, 0x40,
	0x10, 0x85, 0x89, 0x47, 0xee, 0xbc, 0x3d, 0x6c, 0x16, 0x0f, 0x62, 0x17, 0x0e, 0x8b, 0xab, 0xb2,
	0xa8, 0x95, 0x6d, 0xb8, 0xc6, 0xc6, 0x22, 0x82, 0x85, 0x8d, 0xec, 0x65, 0x26, 0xb2, 0xba, 0x3b,
	0xb3, 0x64, 0x27, 0x82, 0xff, 0x5e, 0xb2, 0x82, 0xa8, 0x58, 0xbe, 0x7d, 0xdf, 0xce, 0x37, 0xa3,
	0x6e, 0x1d, 0x0d, 0xa3, 0x35, 0x36, 0x46, 0xa4, 0x17, 0x47, 0x68, 0xfa, 0x91, 0x53, 0x7a, 0xfb,
	0xf0, 0xf6, 0x68, 0x21, 0x38, 0x32, 0x36, 0x3a, 0x33, 0x78, 0x44, 0x31, 0xef, 0x57, 0xa6, 0xe7,
	0x10, 0x98, 0x9a, 0x38, 0xb2, 0xb0, 0xde, 0xfe, 0x41, 0x9b, 0x8c, 0xed, 0x5e, 0xd5, 0xa6, 0x65,
	0x79, 0x40, 0x8f, 0xbd, 0xf0, 0xa8, 0xb7, 0x6a, 0x09, 0x93, 0x3c, 0x3b, 0xa8, 0x8a, 0xba, 0xd8,
	0xaf, 0xbb, 0x12, 0x26, 0xb9, 0x03, 0x7d, 0x50, 0x0a, 0x5c, 0x40, 0x4a, 0x8e, 0x29, 0x55, 0x27,
	0x75, 0xb1, 0xdf, 0x5c, 0x5f, 0x36, 0xff, 0x4e, 0x6c, 0x5a, 0x96, 0xc3, 0x37, 0xdb, 0xfd, 0xf8,
	0xb7, 0x7b, 0x54, 0x67, 0xbf, 0x4a, 0x7d, 0xae, 0xca, 0xc8, 0xec, 0x53, 0x55, 0xd4, 0x8b, 0x59,
	0x96, 0xc3, 0xfc, 0x1a, 0x18, 0xd0, 0x67, 0xcf, 0xba, 0xfb, 0x0a, 0xfa, 0x42, 0x9d, 0xce, 0x9b,
	0x91, 0x0d, 0x58, 0x2d, 0x72, 0xb1, 0x82, 0x49, 0xee, 0x6d, 0xc0, 0x76, 0xf5, 0x54, 0x66, 0xf5,
	0x71, 0x99, 0x4f, 0xbd, 0xf9, 0x0c, 0x00, 0x00, 0xff, 0xff, 0x3c, 0xfb, 0x5c, 0x04, 0x27, 0x01,
	0x00, 0x00,
}
