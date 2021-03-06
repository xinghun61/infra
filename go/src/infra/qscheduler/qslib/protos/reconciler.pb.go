// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/qscheduler/qslib/protos/reconciler.proto

package protos

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
const _ = proto.ProtoPackageIsVersion3 // please upgrade the proto package

// WorkerQueue represents a task request that is pending assignment to a given
// worker and optionally the expected task on the worker to preempt.
//
// Note: the name WorkerQueue is a legacy name, which is why it isn't a great
// match for what it represents.
type WorkerQueue struct {
	// EnqueueTime is the time at which the pending assignment was created
	// by the scheduler.
	EnqueueTime *timestamp.Timestamp `protobuf:"bytes,1,opt,name=enqueue_time,json=enqueueTime,proto3" json:"enqueue_time,omitempty"`
	// TaskToAssign is the id of the task that should be assigned to this worker.
	TaskToAssign string `protobuf:"bytes,2,opt,name=task_to_assign,json=taskToAssign,proto3" json:"task_to_assign,omitempty"`
	// TaskToAbort is the id of the task that should be aborted on this worker.
	//
	// An empty string indicates that there is no task to abort.
	TaskToAbort          string   `protobuf:"bytes,3,opt,name=task_to_abort,json=taskToAbort,proto3" json:"task_to_abort,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *WorkerQueue) Reset()         { *m = WorkerQueue{} }
func (m *WorkerQueue) String() string { return proto.CompactTextString(m) }
func (*WorkerQueue) ProtoMessage()    {}
func (*WorkerQueue) Descriptor() ([]byte, []int) {
	return fileDescriptor_783e774d084cc590, []int{0}
}

func (m *WorkerQueue) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_WorkerQueue.Unmarshal(m, b)
}
func (m *WorkerQueue) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_WorkerQueue.Marshal(b, m, deterministic)
}
func (m *WorkerQueue) XXX_Merge(src proto.Message) {
	xxx_messageInfo_WorkerQueue.Merge(m, src)
}
func (m *WorkerQueue) XXX_Size() int {
	return xxx_messageInfo_WorkerQueue.Size(m)
}
func (m *WorkerQueue) XXX_DiscardUnknown() {
	xxx_messageInfo_WorkerQueue.DiscardUnknown(m)
}

var xxx_messageInfo_WorkerQueue proto.InternalMessageInfo

func (m *WorkerQueue) GetEnqueueTime() *timestamp.Timestamp {
	if m != nil {
		return m.EnqueueTime
	}
	return nil
}

func (m *WorkerQueue) GetTaskToAssign() string {
	if m != nil {
		return m.TaskToAssign
	}
	return ""
}

func (m *WorkerQueue) GetTaskToAbort() string {
	if m != nil {
		return m.TaskToAbort
	}
	return ""
}

// ReconcilerState represents a reconciler. It holds tasks that are pending
// assignment to workers and tasks that have errored out.
type Reconciler struct {
	// WorkerQueues holds pending assignments for workers.
	//
	// An assignment remains pending until a notification from Swarming
	// acknowledges that it has taken place.
	WorkerQueues map[string]*WorkerQueue `protobuf:"bytes,1,rep,name=worker_queues,json=workerQueues,proto3" json:"worker_queues,omitempty" protobuf_key:"bytes,1,opt,name=key,proto3" protobuf_val:"bytes,2,opt,name=value,proto3"`
	// TaskErrors is a map from task ids that had an error to the error description.
	//
	// Task errors remain pending until a notification from Swarming acknowledges
	// that the task is no longer pending.
	TaskErrors           map[string]string `protobuf:"bytes,2,rep,name=task_errors,json=taskErrors,proto3" json:"task_errors,omitempty" protobuf_key:"bytes,1,opt,name=key,proto3" protobuf_val:"bytes,2,opt,name=value,proto3"`
	XXX_NoUnkeyedLiteral struct{}          `json:"-"`
	XXX_unrecognized     []byte            `json:"-"`
	XXX_sizecache        int32             `json:"-"`
}

func (m *Reconciler) Reset()         { *m = Reconciler{} }
func (m *Reconciler) String() string { return proto.CompactTextString(m) }
func (*Reconciler) ProtoMessage()    {}
func (*Reconciler) Descriptor() ([]byte, []int) {
	return fileDescriptor_783e774d084cc590, []int{1}
}

func (m *Reconciler) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Reconciler.Unmarshal(m, b)
}
func (m *Reconciler) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Reconciler.Marshal(b, m, deterministic)
}
func (m *Reconciler) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Reconciler.Merge(m, src)
}
func (m *Reconciler) XXX_Size() int {
	return xxx_messageInfo_Reconciler.Size(m)
}
func (m *Reconciler) XXX_DiscardUnknown() {
	xxx_messageInfo_Reconciler.DiscardUnknown(m)
}

var xxx_messageInfo_Reconciler proto.InternalMessageInfo

func (m *Reconciler) GetWorkerQueues() map[string]*WorkerQueue {
	if m != nil {
		return m.WorkerQueues
	}
	return nil
}

func (m *Reconciler) GetTaskErrors() map[string]string {
	if m != nil {
		return m.TaskErrors
	}
	return nil
}

func init() {
	proto.RegisterType((*WorkerQueue)(nil), "protos.WorkerQueue")
	proto.RegisterType((*Reconciler)(nil), "protos.Reconciler")
	proto.RegisterMapType((map[string]string)(nil), "protos.Reconciler.TaskErrorsEntry")
	proto.RegisterMapType((map[string]*WorkerQueue)(nil), "protos.Reconciler.WorkerQueuesEntry")
}

func init() {
	proto.RegisterFile("infra/qscheduler/qslib/protos/reconciler.proto", fileDescriptor_783e774d084cc590)
}

var fileDescriptor_783e774d084cc590 = []byte{
	// 330 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x6c, 0x91, 0xcd, 0x4a, 0xf3, 0x40,
	0x14, 0x86, 0x49, 0xca, 0xf7, 0x41, 0x4f, 0x5a, 0x7f, 0x46, 0x17, 0x21, 0x1b, 0x4b, 0xe8, 0xa2,
	0x6e, 0x26, 0x50, 0x37, 0x22, 0x74, 0x21, 0xd2, 0x85, 0x4b, 0x43, 0xc0, 0x65, 0x48, 0xea, 0x69,
	0x0d, 0x49, 0x33, 0xed, 0x9c, 0x89, 0xa5, 0x37, 0xe2, 0x7d, 0x78, 0x87, 0x32, 0x33, 0x6d, 0x0c,
	0xda, 0xdd, 0xf0, 0xe6, 0x99, 0xe7, 0x9d, 0x73, 0x02, 0xbc, 0xa8, 0x97, 0x32, 0x8b, 0xb6, 0xb4,
	0x78, 0xc7, 0xb7, 0xa6, 0x42, 0x19, 0x6d, 0xa9, 0x2a, 0xf2, 0x68, 0x23, 0x85, 0x12, 0x14, 0x49,
	0x5c, 0x88, 0x7a, 0x51, 0x54, 0x28, 0xb9, 0x49, 0xd8, 0x7f, 0xfb, 0x21, 0xb8, 0x59, 0x09, 0xb1,
	0xaa, 0xd0, 0x72, 0x79, 0xb3, 0x8c, 0x54, 0xb1, 0x46, 0x52, 0xd9, 0x7a, 0x63, 0xc1, 0xf0, 0xd3,
	0x01, 0xef, 0x55, 0xc8, 0x12, 0xe5, 0x4b, 0x83, 0x0d, 0xb2, 0x19, 0x0c, 0xb0, 0xde, 0xea, 0x63,
	0xaa, 0x51, 0xdf, 0x19, 0x39, 0x13, 0x6f, 0x1a, 0x70, 0xeb, 0xe1, 0x47, 0x0f, 0x4f, 0x8e, 0x9e,
	0xd8, 0x3b, 0xf0, 0x3a, 0x61, 0x63, 0x38, 0x53, 0x19, 0x95, 0xa9, 0x12, 0x69, 0x46, 0x54, 0xac,
	0x6a, 0xdf, 0x1d, 0x39, 0x93, 0x7e, 0x3c, 0xd0, 0x69, 0x22, 0x1e, 0x4d, 0xc6, 0x42, 0x18, 0xb6,
	0x54, 0x2e, 0xa4, 0xf2, 0x7b, 0x06, 0xf2, 0x0e, 0x90, 0x8e, 0xc2, 0x2f, 0x17, 0x20, 0x6e, 0xc7,
	0x62, 0xcf, 0x30, 0xdc, 0x99, 0x67, 0xa6, 0xa6, 0x8c, 0x7c, 0x67, 0xd4, 0x9b, 0x78, 0xd3, 0xb1,
	0x7d, 0x11, 0xf1, 0x1f, 0x94, 0x77, 0xc6, 0xa1, 0x79, 0xad, 0xe4, 0x3e, 0x1e, 0xec, 0x3a, 0x11,
	0x7b, 0x02, 0x53, 0x94, 0xa2, 0x94, 0x42, 0x92, 0xef, 0x1a, 0x51, 0x78, 0x42, 0x94, 0x64, 0x54,
	0xce, 0x0d, 0x64, 0x35, 0xa0, 0xda, 0x20, 0x48, 0xe0, 0xf2, 0x4f, 0x0f, 0xbb, 0x80, 0x5e, 0x89,
	0x7b, 0xb3, 0xb3, 0x7e, 0xac, 0x8f, 0xec, 0x16, 0xfe, 0x7d, 0x64, 0x55, 0x83, 0x66, 0x0d, 0xde,
	0xf4, 0xea, 0xd8, 0xd2, 0xb9, 0x1b, 0x5b, 0xe2, 0xc1, 0xbd, 0x77, 0x82, 0x19, 0x9c, 0xff, 0x2a,
	0x3d, 0xe1, 0xbc, 0xee, 0x3a, 0xfb, 0x9d, 0xeb, 0xb9, 0xfd, 0xeb, 0x77, 0xdf, 0x01, 0x00, 0x00,
	0xff, 0xff, 0x83, 0xb5, 0x52, 0xde, 0x2e, 0x02, 0x00, 0x00,
}
