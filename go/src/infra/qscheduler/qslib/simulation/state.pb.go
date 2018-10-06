// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/qscheduler/qslib/simulation/state.proto

package simulation

import (
	fmt "fmt"
	math "math"

	proto "github.com/golang/protobuf/proto"
	timestamp "github.com/golang/protobuf/ptypes/timestamp"
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

// Generator represents the state of a workload generator.
//
// The configuration for a generator is a Workload object.
type Generator struct {
	// NextCycle is the next time at which this generator will emit
	// requests.
	NextCycle *timestamp.Timestamp `protobuf:"bytes,1,opt,name=next_cycle,json=nextCycle,proto3" json:"next_cycle,omitempty"`
	// LabelSetRemaining is the number of cycles remaining for the current LabelSet.
	LabelSetRemaining int32 `protobuf:"varint,2,opt,name=label_set_remaining,json=labelSetRemaining,proto3" json:"label_set_remaining,omitempty"`
	// LabelSetId is will be combined with and on the Workload Tag to create a
	// unique LabelSet.
	LabelSetId int32 `protobuf:"varint,3,opt,name=label_set_id,json=labelSetId,proto3" json:"label_set_id,omitempty"`
	// ReqCount is the integer id of the current request.
	ReqCount             int32    `protobuf:"varint,4,opt,name=req_count,json=reqCount,proto3" json:"req_count,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Generator) Reset()         { *m = Generator{} }
func (m *Generator) String() string { return proto.CompactTextString(m) }
func (*Generator) ProtoMessage()    {}
func (*Generator) Descriptor() ([]byte, []int) {
	return fileDescriptor_e8df602498159471, []int{0}
}

func (m *Generator) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Generator.Unmarshal(m, b)
}
func (m *Generator) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Generator.Marshal(b, m, deterministic)
}
func (m *Generator) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Generator.Merge(m, src)
}
func (m *Generator) XXX_Size() int {
	return xxx_messageInfo_Generator.Size(m)
}
func (m *Generator) XXX_DiscardUnknown() {
	xxx_messageInfo_Generator.DiscardUnknown(m)
}

var xxx_messageInfo_Generator proto.InternalMessageInfo

func (m *Generator) GetNextCycle() *timestamp.Timestamp {
	if m != nil {
		return m.NextCycle
	}
	return nil
}

func (m *Generator) GetLabelSetRemaining() int32 {
	if m != nil {
		return m.LabelSetRemaining
	}
	return 0
}

func (m *Generator) GetLabelSetId() int32 {
	if m != nil {
		return m.LabelSetId
	}
	return 0
}

func (m *Generator) GetReqCount() int32 {
	if m != nil {
		return m.ReqCount
	}
	return 0
}

func init() {
	proto.RegisterType((*Generator)(nil), "simulation.Generator")
}

func init() {
	proto.RegisterFile("infra/qscheduler/qslib/simulation/state.proto", fileDescriptor_e8df602498159471)
}

var fileDescriptor_e8df602498159471 = []byte{
	// 224 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x44, 0xce, 0xbf, 0x4e, 0xc3, 0x30,
	0x10, 0xc7, 0x71, 0x85, 0x7f, 0x22, 0x07, 0x0b, 0x66, 0x89, 0xca, 0x40, 0xc4, 0xd4, 0x05, 0x5b,
	0x82, 0x89, 0xb9, 0x03, 0x62, 0x0d, 0xec, 0x91, 0x93, 0x5c, 0xc3, 0x49, 0x8e, 0xdd, 0x9c, 0x2f,
	0x12, 0x3c, 0x18, 0xef, 0x87, 0xe2, 0xca, 0xea, 0x68, 0x7f, 0x3f, 0xfa, 0xe9, 0xe0, 0x99, 0xfc,
	0x9e, 0xad, 0x99, 0x63, 0xff, 0x8d, 0xc3, 0xe2, 0x90, 0xcd, 0x1c, 0x1d, 0x75, 0x26, 0xd2, 0xb4,
	0x38, 0x2b, 0x14, 0xbc, 0x89, 0x62, 0x05, 0xf5, 0x81, 0x83, 0x04, 0x05, 0xa7, 0xff, 0xcd, 0xe3,
	0x18, 0xc2, 0xe8, 0xd0, 0xa4, 0xd2, 0x2d, 0x7b, 0x23, 0x34, 0x61, 0x14, 0x3b, 0x1d, 0x8e, 0xf8,
	0xe9, 0xaf, 0x80, 0xf2, 0x1d, 0x3d, 0xb2, 0x95, 0xc0, 0xea, 0x0d, 0xc0, 0xe3, 0x8f, 0xb4, 0xfd,
	0x6f, 0xef, 0xb0, 0x2a, 0xea, 0x62, 0x7b, 0xf3, 0xb2, 0xd1, 0xc7, 0x0d, 0x9d, 0x37, 0xf4, 0x57,
	0xde, 0x68, 0xca, 0x55, 0xef, 0x56, 0xac, 0x34, 0xdc, 0x3b, 0xdb, 0xa1, 0x6b, 0x23, 0x4a, 0xcb,
	0x38, 0x59, 0xf2, 0xe4, 0xc7, 0xea, 0xac, 0x2e, 0xb6, 0x97, 0xcd, 0x5d, 0x4a, 0x9f, 0x28, 0x4d,
	0x0e, 0xaa, 0x86, 0xdb, 0x93, 0xa7, 0xa1, 0x3a, 0x4f, 0x10, 0x32, 0xfc, 0x18, 0xd4, 0x03, 0x94,
	0x8c, 0x73, 0xdb, 0x87, 0xc5, 0x4b, 0x75, 0x91, 0xf2, 0x35, 0xe3, 0xbc, 0x5b, 0xdf, 0xdd, 0x55,
	0xba, 0xe6, 0xf5, 0x3f, 0x00, 0x00, 0xff, 0xff, 0x4c, 0x4a, 0xb1, 0x13, 0x1c, 0x01, 0x00, 0x00,
}
