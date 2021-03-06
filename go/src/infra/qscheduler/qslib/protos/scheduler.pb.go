// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/qscheduler/qslib/protos/scheduler.proto

package protos

import (
	fmt "fmt"
	math "math"

	proto "github.com/golang/protobuf/proto"
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

// Scheduler encapsulates the state and configuration of a running
// quotascheduler for a single pool.
type Scheduler struct {
	// SchedulerState is the state of the scheduler.
	State *SchedulerState `protobuf:"bytes,1,opt,name=state,proto3" json:"state,omitempty"`
	// SchedulerConfig is the config of the scheduler.
	Config               *SchedulerConfig `protobuf:"bytes,2,opt,name=config,proto3" json:"config,omitempty"`
	XXX_NoUnkeyedLiteral struct{}         `json:"-"`
	XXX_unrecognized     []byte           `json:"-"`
	XXX_sizecache        int32            `json:"-"`
}

func (m *Scheduler) Reset()         { *m = Scheduler{} }
func (m *Scheduler) String() string { return proto.CompactTextString(m) }
func (*Scheduler) ProtoMessage()    {}
func (*Scheduler) Descriptor() ([]byte, []int) {
	return fileDescriptor_d8186a34c82ee198, []int{0}
}

func (m *Scheduler) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Scheduler.Unmarshal(m, b)
}
func (m *Scheduler) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Scheduler.Marshal(b, m, deterministic)
}
func (m *Scheduler) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Scheduler.Merge(m, src)
}
func (m *Scheduler) XXX_Size() int {
	return xxx_messageInfo_Scheduler.Size(m)
}
func (m *Scheduler) XXX_DiscardUnknown() {
	xxx_messageInfo_Scheduler.DiscardUnknown(m)
}

var xxx_messageInfo_Scheduler proto.InternalMessageInfo

func (m *Scheduler) GetState() *SchedulerState {
	if m != nil {
		return m.State
	}
	return nil
}

func (m *Scheduler) GetConfig() *SchedulerConfig {
	if m != nil {
		return m.Config
	}
	return nil
}

func init() {
	proto.RegisterType((*Scheduler)(nil), "protos.Scheduler")
}

func init() {
	proto.RegisterFile("infra/qscheduler/qslib/protos/scheduler.proto", fileDescriptor_d8186a34c82ee198)
}

var fileDescriptor_d8186a34c82ee198 = []byte{
	// 144 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0xe2, 0xd2, 0xcd, 0xcc, 0x4b, 0x2b,
	0x4a, 0xd4, 0x2f, 0x2c, 0x4e, 0xce, 0x48, 0x4d, 0x29, 0xcd, 0x49, 0x2d, 0xd2, 0x2f, 0x2c, 0xce,
	0xc9, 0x4c, 0xd2, 0x2f, 0x28, 0xca, 0x2f, 0xc9, 0x2f, 0xd6, 0x87, 0x0b, 0xeb, 0x81, 0x05, 0x84,
	0xd8, 0x20, 0xe2, 0x52, 0x9a, 0x04, 0xb4, 0x95, 0x24, 0x96, 0xa4, 0x42, 0xb4, 0x48, 0x69, 0xe1,
	0x57, 0x9a, 0x9c, 0x9f, 0x97, 0x96, 0x99, 0x0e, 0x51, 0xab, 0x94, 0xc5, 0xc5, 0x19, 0x0c, 0x53,
	0x26, 0xa4, 0xc3, 0xc5, 0x0a, 0x36, 0x47, 0x82, 0x51, 0x81, 0x51, 0x83, 0xdb, 0x48, 0x0c, 0xa2,
	0xa6, 0x58, 0x0f, 0xae, 0x22, 0x18, 0x24, 0x1b, 0x04, 0x51, 0x24, 0xa4, 0xcf, 0xc5, 0x06, 0x31,
	0x4a, 0x82, 0x09, 0xac, 0x5c, 0x1c, 0x43, 0xb9, 0x33, 0x58, 0x3a, 0x08, 0xaa, 0x2c, 0x09, 0xe2,
	0x15, 0x63, 0x40, 0x00, 0x00, 0x00, 0xff, 0xff, 0x32, 0xb3, 0xd7, 0x20, 0x02, 0x01, 0x00, 0x00,
}
