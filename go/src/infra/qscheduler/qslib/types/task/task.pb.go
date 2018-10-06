// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/qscheduler/qslib/types/task/task.proto

package task

import (
	fmt "fmt"
	vector "infra/qscheduler/qslib/types/vector"
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

// Request represents a requested task in the queue, and refers to the
// quota account to run it against. This representation intentionally
// excludes most of the details of a Swarming task request.
type Request struct {
	// AccountId is the id of the account that this request charges to.
	AccountId string `protobuf:"bytes,1,opt,name=account_id,json=accountId,proto3" json:"account_id,omitempty"`
	// EnqueueTime is the time at which the request was enqueued.
	EnqueueTime *timestamp.Timestamp `protobuf:"bytes,2,opt,name=enqueue_time,json=enqueueTime,proto3" json:"enqueue_time,omitempty"`
	// The set of Provisionable Labels for this task.
	Labels               []string `protobuf:"bytes,3,rep,name=labels,proto3" json:"labels,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Request) Reset()         { *m = Request{} }
func (m *Request) String() string { return proto.CompactTextString(m) }
func (*Request) ProtoMessage()    {}
func (*Request) Descriptor() ([]byte, []int) {
	return fileDescriptor_d30de70d95288ebe, []int{0}
}

func (m *Request) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Request.Unmarshal(m, b)
}
func (m *Request) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Request.Marshal(b, m, deterministic)
}
func (m *Request) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Request.Merge(m, src)
}
func (m *Request) XXX_Size() int {
	return xxx_messageInfo_Request.Size(m)
}
func (m *Request) XXX_DiscardUnknown() {
	xxx_messageInfo_Request.DiscardUnknown(m)
}

var xxx_messageInfo_Request proto.InternalMessageInfo

func (m *Request) GetAccountId() string {
	if m != nil {
		return m.AccountId
	}
	return ""
}

func (m *Request) GetEnqueueTime() *timestamp.Timestamp {
	if m != nil {
		return m.EnqueueTime
	}
	return nil
}

func (m *Request) GetLabels() []string {
	if m != nil {
		return m.Labels
	}
	return nil
}

// Run represents a task that has been assigned to a worker and is
// now running.
type Run struct {
	// Cost is the total cost that has been incurred on this task while running.
	Cost *vector.Vector `protobuf:"bytes,1,opt,name=cost,proto3" json:"cost,omitempty"`
	// Request is the request that this running task corresponds to.
	Request *Request `protobuf:"bytes,2,opt,name=request,proto3" json:"request,omitempty"`
	// RequestId is the request id of the request that this running task
	// corresponds to.
	RequestId string `protobuf:"bytes,3,opt,name=request_id,json=requestId,proto3" json:"request_id,omitempty"`
	// Priority is the current priority level of the running task.
	Priority             int32    `protobuf:"varint,4,opt,name=priority,proto3" json:"priority,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Run) Reset()         { *m = Run{} }
func (m *Run) String() string { return proto.CompactTextString(m) }
func (*Run) ProtoMessage()    {}
func (*Run) Descriptor() ([]byte, []int) {
	return fileDescriptor_d30de70d95288ebe, []int{1}
}

func (m *Run) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Run.Unmarshal(m, b)
}
func (m *Run) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Run.Marshal(b, m, deterministic)
}
func (m *Run) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Run.Merge(m, src)
}
func (m *Run) XXX_Size() int {
	return xxx_messageInfo_Run.Size(m)
}
func (m *Run) XXX_DiscardUnknown() {
	xxx_messageInfo_Run.DiscardUnknown(m)
}

var xxx_messageInfo_Run proto.InternalMessageInfo

func (m *Run) GetCost() *vector.Vector {
	if m != nil {
		return m.Cost
	}
	return nil
}

func (m *Run) GetRequest() *Request {
	if m != nil {
		return m.Request
	}
	return nil
}

func (m *Run) GetRequestId() string {
	if m != nil {
		return m.RequestId
	}
	return ""
}

func (m *Run) GetPriority() int32 {
	if m != nil {
		return m.Priority
	}
	return 0
}

func init() {
	proto.RegisterType((*Request)(nil), "task.Request")
	proto.RegisterType((*Run)(nil), "task.Run")
}

func init() {
	proto.RegisterFile("infra/qscheduler/qslib/types/task/task.proto", fileDescriptor_d30de70d95288ebe)
}

var fileDescriptor_d30de70d95288ebe = []byte{
	// 278 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x7c, 0x90, 0xbf, 0x4e, 0xc3, 0x30,
	0x10, 0xc6, 0x15, 0x52, 0x5a, 0xe2, 0x00, 0x83, 0x07, 0x14, 0x45, 0x42, 0x44, 0x59, 0xc8, 0x80,
	0x6c, 0x54, 0x66, 0x1e, 0xa0, 0xab, 0x85, 0x58, 0xab, 0xfc, 0xb9, 0x16, 0x8b, 0x34, 0x4e, 0xec,
	0x33, 0x52, 0x27, 0x9e, 0x80, 0x77, 0x46, 0xb1, 0x1d, 0x46, 0x16, 0xdf, 0xdd, 0x77, 0x67, 0xdf,
	0xf7, 0x33, 0x79, 0x92, 0xc3, 0x41, 0xd7, 0x7c, 0x32, 0xed, 0x07, 0x74, 0xb6, 0x07, 0xcd, 0x27,
	0xd3, 0xcb, 0x86, 0xe3, 0x79, 0x04, 0xc3, 0xb1, 0x36, 0x9f, 0xee, 0x60, 0xa3, 0x56, 0xa8, 0xe8,
	0x6a, 0xce, 0xf3, 0x87, 0xa3, 0x52, 0xc7, 0x1e, 0xb8, 0xd3, 0x1a, 0x7b, 0xe0, 0x28, 0x4f, 0x60,
	0xb0, 0x3e, 0x8d, 0x7e, 0x2c, 0x7f, 0xfe, 0xf7, 0xd1, 0x2f, 0x68, 0x51, 0xe9, 0x10, 0xfc, 0x8d,
	0xf2, 0x9b, 0x6c, 0x04, 0x4c, 0x16, 0x0c, 0xd2, 0x7b, 0x42, 0xea, 0xb6, 0x55, 0x76, 0xc0, 0xbd,
	0xec, 0xb2, 0xa8, 0x88, 0xaa, 0x44, 0x24, 0x41, 0xd9, 0x75, 0xf4, 0x95, 0x5c, 0xc3, 0x30, 0x59,
	0xb0, 0xb0, 0x9f, 0xd7, 0x66, 0x17, 0x45, 0x54, 0xa5, 0xdb, 0x9c, 0x79, 0x4f, 0x6c, 0xf1, 0xc4,
	0xde, 0x16, 0x4f, 0x22, 0x0d, 0xf3, 0xb3, 0x42, 0xef, 0xc8, 0xba, 0xaf, 0x1b, 0xe8, 0x4d, 0x16,
	0x17, 0x71, 0x95, 0x88, 0x50, 0x95, 0x3f, 0x11, 0x89, 0x85, 0x1d, 0x68, 0x49, 0x56, 0xad, 0x32,
	0xe8, 0xf6, 0xa6, 0xdb, 0x5b, 0x16, 0x5c, 0xbe, 0xbb, 0x20, 0x5c, 0x8f, 0x3e, 0x92, 0x8d, 0xf6,
	0x66, 0xc3, 0xf6, 0x1b, 0xe6, 0xfe, 0x28, 0x10, 0x88, 0xa5, 0x3b, 0xa3, 0x84, 0x74, 0x46, 0x89,
	0x3d, 0x4a, 0x50, 0x76, 0x1d, 0xcd, 0xc9, 0xd5, 0xa8, 0xa5, 0xd2, 0x12, 0xcf, 0xd9, 0xaa, 0x88,
	0xaa, 0x4b, 0xf1, 0x57, 0x37, 0x6b, 0x07, 0xf2, 0xf2, 0x1b, 0x00, 0x00, 0xff, 0xff, 0x16, 0x10,
	0xd3, 0x19, 0xa0, 0x01, 0x00, 0x00,
}
