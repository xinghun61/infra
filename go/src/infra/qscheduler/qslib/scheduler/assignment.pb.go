// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/qscheduler/qslib/scheduler/assignment.proto

package scheduler

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

type Assignment_Type int32

const (
	// Assign a task to a currently idle worker.
	Assignment_IDLE_WORKER Assignment_Type = 0
	// Preempt a running task on a worker with a new task.
	Assignment_PREEMPT_WORKER Assignment_Type = 1
)

var Assignment_Type_name = map[int32]string{
	0: "IDLE_WORKER",
	1: "PREEMPT_WORKER",
}

var Assignment_Type_value = map[string]int32{
	"IDLE_WORKER":    0,
	"PREEMPT_WORKER": 1,
}

func (x Assignment_Type) String() string {
	return proto.EnumName(Assignment_Type_name, int32(x))
}

func (Assignment_Type) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_fcbc6dd4eb727ef1, []int{0, 0}
}

// An Assignment represents a scheduler decision to assign a task
// to a worker.
type Assignment struct {
	// Type describes which kind of assignment this represents.
	Type Assignment_Type `protobuf:"varint,1,opt,name=type,proto3,enum=scheduler.Assignment_Type" json:"type,omitempty"`
	// WorkerId of the worker to assign a new task to (and to preempt the previous
	// task of, if this is a PREEMPT_WORKER mutator).
	WorkerId string `protobuf:"bytes,2,opt,name=worker_id,json=workerId,proto3" json:"worker_id,omitempty"`
	// RequestId of the task to assign to that worker.
	RequestId string `protobuf:"bytes,3,opt,name=request_id,json=requestId,proto3" json:"request_id,omitempty"`
	// TaskToAbort is relevant only for the PREEMPT_WORKER type.
	// It is the request ID of the task that should be preempted.
	TaskToAbort string `protobuf:"bytes,4,opt,name=task_to_abort,json=taskToAbort,proto3" json:"task_to_abort,omitempty"`
	// Priority at which the task will run.
	Priority int32 `protobuf:"varint,5,opt,name=priority,proto3" json:"priority,omitempty"`
	// Time is the time at which this Assignment was determined.
	Time                 *timestamp.Timestamp `protobuf:"bytes,6,opt,name=time,proto3" json:"time,omitempty"`
	XXX_NoUnkeyedLiteral struct{}             `json:"-"`
	XXX_unrecognized     []byte               `json:"-"`
	XXX_sizecache        int32                `json:"-"`
}

func (m *Assignment) Reset()         { *m = Assignment{} }
func (m *Assignment) String() string { return proto.CompactTextString(m) }
func (*Assignment) ProtoMessage()    {}
func (*Assignment) Descriptor() ([]byte, []int) {
	return fileDescriptor_fcbc6dd4eb727ef1, []int{0}
}

func (m *Assignment) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Assignment.Unmarshal(m, b)
}
func (m *Assignment) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Assignment.Marshal(b, m, deterministic)
}
func (m *Assignment) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Assignment.Merge(m, src)
}
func (m *Assignment) XXX_Size() int {
	return xxx_messageInfo_Assignment.Size(m)
}
func (m *Assignment) XXX_DiscardUnknown() {
	xxx_messageInfo_Assignment.DiscardUnknown(m)
}

var xxx_messageInfo_Assignment proto.InternalMessageInfo

func (m *Assignment) GetType() Assignment_Type {
	if m != nil {
		return m.Type
	}
	return Assignment_IDLE_WORKER
}

func (m *Assignment) GetWorkerId() string {
	if m != nil {
		return m.WorkerId
	}
	return ""
}

func (m *Assignment) GetRequestId() string {
	if m != nil {
		return m.RequestId
	}
	return ""
}

func (m *Assignment) GetTaskToAbort() string {
	if m != nil {
		return m.TaskToAbort
	}
	return ""
}

func (m *Assignment) GetPriority() int32 {
	if m != nil {
		return m.Priority
	}
	return 0
}

func (m *Assignment) GetTime() *timestamp.Timestamp {
	if m != nil {
		return m.Time
	}
	return nil
}

func init() {
	proto.RegisterEnum("scheduler.Assignment_Type", Assignment_Type_name, Assignment_Type_value)
	proto.RegisterType((*Assignment)(nil), "scheduler.Assignment")
}

func init() {
	proto.RegisterFile("infra/qscheduler/qslib/scheduler/assignment.proto", fileDescriptor_fcbc6dd4eb727ef1)
}

var fileDescriptor_fcbc6dd4eb727ef1 = []byte{
	// 282 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x44, 0x8f, 0xd1, 0x6a, 0xb3, 0x30,
	0x18, 0x86, 0xff, 0xf4, 0x6f, 0x4b, 0xfd, 0xca, 0xba, 0x91, 0x23, 0x71, 0x8c, 0x89, 0x47, 0xc2,
	0x20, 0xb2, 0xee, 0x0a, 0x0a, 0xf3, 0x40, 0xb6, 0xb1, 0x12, 0x84, 0x1d, 0x8a, 0xce, 0xd4, 0x85,
	0xaa, 0xd1, 0x24, 0x32, 0xbc, 0x90, 0xdd, 0xef, 0x30, 0x4e, 0x7b, 0xf8, 0x3d, 0xef, 0xc3, 0xcb,
	0xf7, 0xc2, 0x23, 0xaf, 0x4f, 0x32, 0x0d, 0x5a, 0xf5, 0xf9, 0xc5, 0xf2, 0xae, 0x64, 0x32, 0x68,
	0x55, 0xc9, 0xb3, 0xe0, 0x72, 0xa7, 0x4a, 0xf1, 0xa2, 0xae, 0x58, 0xad, 0x49, 0x23, 0x85, 0x16,
	0xd8, 0x9a, 0x33, 0xe7, 0xbe, 0x10, 0xa2, 0x28, 0x59, 0x60, 0x82, 0xac, 0x3b, 0x05, 0x9a, 0x57,
	0x4c, 0xe9, 0xb4, 0x6a, 0x46, 0xd7, 0xfb, 0x59, 0x00, 0x1c, 0xe6, 0x02, 0x4c, 0x60, 0xa9, 0xfb,
	0x86, 0xd9, 0xc8, 0x45, 0xfe, 0x6e, 0xef, 0x90, 0xb9, 0x89, 0x5c, 0x24, 0x12, 0xf7, 0x0d, 0xa3,
	0xc6, 0xc3, 0xb7, 0x60, 0x7d, 0x0b, 0x79, 0x66, 0x32, 0xe1, 0xb9, 0xbd, 0x70, 0x91, 0x6f, 0xd1,
	0xcd, 0x08, 0xa2, 0x1c, 0xdf, 0x01, 0x48, 0xd6, 0x76, 0x4c, 0xe9, 0x21, 0xfd, 0x6f, 0x52, 0xeb,
	0x8f, 0x44, 0x39, 0xf6, 0xe0, 0x4a, 0xa7, 0xea, 0x9c, 0x68, 0x91, 0xa4, 0x99, 0x90, 0xda, 0x5e,
	0x1a, 0x63, 0x3b, 0xc0, 0x58, 0x1c, 0x06, 0x84, 0x1d, 0xd8, 0x34, 0x92, 0x0b, 0xc9, 0x75, 0x6f,
	0xaf, 0x5c, 0xe4, 0xaf, 0xe8, 0x7c, 0x9b, 0x5f, 0x79, 0xc5, 0xec, 0xb5, 0x8b, 0xfc, 0xed, 0xde,
	0x21, 0xe3, 0x54, 0x32, 0x4d, 0x25, 0xf1, 0x34, 0x95, 0x1a, 0xcf, 0x7b, 0x80, 0xe5, 0xf0, 0x39,
	0xbe, 0x86, 0x6d, 0xf4, 0xfc, 0x1a, 0x26, 0x1f, 0xef, 0xf4, 0x25, 0xa4, 0x37, 0xff, 0x30, 0x86,
	0xdd, 0x91, 0x86, 0xe1, 0xdb, 0x31, 0x9e, 0x18, 0xca, 0xd6, 0xa6, 0xe6, 0xe9, 0x37, 0x00, 0x00,
	0xff, 0xff, 0xa4, 0x60, 0x12, 0x9d, 0x7f, 0x01, 0x00, 0x00,
}
