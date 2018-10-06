// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/qscheduler/qslib/scheduler/scheduler.proto

package scheduler

import (
	fmt "fmt"
	account "infra/qscheduler/qslib/types/account"
	task "infra/qscheduler/qslib/types/task"
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

// Worker represents a resource that can run 1 task at a time. This corresponds
// to the swarming concept of a Bot. This representation considers only the
// subset of Labels that are Provisionable (can be changed by running a task),
// because the quota scheduler algorithm is expected to run against a pool of
// otherwise homogenous workers.
type Worker struct {
	// Labels represents the set of provisionable labels that this worker
	// possesses.
	Labels []string `protobuf:"bytes,1,rep,name=labels,proto3" json:"labels,omitempty"`
	// RunningTask is, if non-nil, the task that is currently running on the
	// worker.
	RunningTask          *task.Run `protobuf:"bytes,2,opt,name=running_task,json=runningTask,proto3" json:"running_task,omitempty"`
	XXX_NoUnkeyedLiteral struct{}  `json:"-"`
	XXX_unrecognized     []byte    `json:"-"`
	XXX_sizecache        int32     `json:"-"`
}

func (m *Worker) Reset()         { *m = Worker{} }
func (m *Worker) String() string { return proto.CompactTextString(m) }
func (*Worker) ProtoMessage()    {}
func (*Worker) Descriptor() ([]byte, []int) {
	return fileDescriptor_9c9a368e1d01bf8a, []int{0}
}

func (m *Worker) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Worker.Unmarshal(m, b)
}
func (m *Worker) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Worker.Marshal(b, m, deterministic)
}
func (m *Worker) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Worker.Merge(m, src)
}
func (m *Worker) XXX_Size() int {
	return xxx_messageInfo_Worker.Size(m)
}
func (m *Worker) XXX_DiscardUnknown() {
	xxx_messageInfo_Worker.DiscardUnknown(m)
}

var xxx_messageInfo_Worker proto.InternalMessageInfo

func (m *Worker) GetLabels() []string {
	if m != nil {
		return m.Labels
	}
	return nil
}

func (m *Worker) GetRunningTask() *task.Run {
	if m != nil {
		return m.RunningTask
	}
	return nil
}

// State represents the overall state of a quota scheduler worker pool,
// account set, and task queue. This is represented separately from
// configuration information. The state is expected to be updated frequently,
// on each scheduler tick.
type State struct {
	// Requests that are waiting to be assigned to a worker, keyed by
	// request id.
	Requests map[string]*task.Request `protobuf:"bytes,1,rep,name=requests,proto3" json:"requests,omitempty" protobuf_key:"bytes,1,opt,name=key,proto3" protobuf_val:"bytes,2,opt,name=value,proto3"`
	// Balance of all quota accounts for this pool, keyed by account id.
	Balances map[string]*vector.Vector `protobuf:"bytes,2,rep,name=balances,proto3" json:"balances,omitempty" protobuf_key:"bytes,1,opt,name=key,proto3" protobuf_val:"bytes,2,opt,name=value,proto3"`
	// Workers that may run tasks, and their states, keyed by worker id.
	Workers map[string]*Worker `protobuf:"bytes,3,rep,name=workers,proto3" json:"workers,omitempty" protobuf_key:"bytes,1,opt,name=key,proto3" protobuf_val:"bytes,2,opt,name=value,proto3"`
	// LastUpdateTime is the last time at which UpdateTime was called on a scheduler,
	// and corresponds to the when the quota account balances were updated.
	LastUpdateTime       *timestamp.Timestamp `protobuf:"bytes,4,opt,name=last_update_time,json=lastUpdateTime,proto3" json:"last_update_time,omitempty"`
	XXX_NoUnkeyedLiteral struct{}             `json:"-"`
	XXX_unrecognized     []byte               `json:"-"`
	XXX_sizecache        int32                `json:"-"`
}

func (m *State) Reset()         { *m = State{} }
func (m *State) String() string { return proto.CompactTextString(m) }
func (*State) ProtoMessage()    {}
func (*State) Descriptor() ([]byte, []int) {
	return fileDescriptor_9c9a368e1d01bf8a, []int{1}
}

func (m *State) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_State.Unmarshal(m, b)
}
func (m *State) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_State.Marshal(b, m, deterministic)
}
func (m *State) XXX_Merge(src proto.Message) {
	xxx_messageInfo_State.Merge(m, src)
}
func (m *State) XXX_Size() int {
	return xxx_messageInfo_State.Size(m)
}
func (m *State) XXX_DiscardUnknown() {
	xxx_messageInfo_State.DiscardUnknown(m)
}

var xxx_messageInfo_State proto.InternalMessageInfo

func (m *State) GetRequests() map[string]*task.Request {
	if m != nil {
		return m.Requests
	}
	return nil
}

func (m *State) GetBalances() map[string]*vector.Vector {
	if m != nil {
		return m.Balances
	}
	return nil
}

func (m *State) GetWorkers() map[string]*Worker {
	if m != nil {
		return m.Workers
	}
	return nil
}

func (m *State) GetLastUpdateTime() *timestamp.Timestamp {
	if m != nil {
		return m.LastUpdateTime
	}
	return nil
}

// Config represents configuration information about the behavior of accounts
// for this quota scheduler pool.
type Config struct {
	// Configuration for a given account, keyed by account id.
	AccountConfigs       map[string]*account.Config `protobuf:"bytes,1,rep,name=account_configs,json=accountConfigs,proto3" json:"account_configs,omitempty" protobuf_key:"bytes,1,opt,name=key,proto3" protobuf_val:"bytes,2,opt,name=value,proto3"`
	XXX_NoUnkeyedLiteral struct{}                   `json:"-"`
	XXX_unrecognized     []byte                     `json:"-"`
	XXX_sizecache        int32                      `json:"-"`
}

func (m *Config) Reset()         { *m = Config{} }
func (m *Config) String() string { return proto.CompactTextString(m) }
func (*Config) ProtoMessage()    {}
func (*Config) Descriptor() ([]byte, []int) {
	return fileDescriptor_9c9a368e1d01bf8a, []int{2}
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

func (m *Config) GetAccountConfigs() map[string]*account.Config {
	if m != nil {
		return m.AccountConfigs
	}
	return nil
}

func init() {
	proto.RegisterType((*Worker)(nil), "scheduler.Worker")
	proto.RegisterType((*State)(nil), "scheduler.State")
	proto.RegisterMapType((map[string]*vector.Vector)(nil), "scheduler.State.BalancesEntry")
	proto.RegisterMapType((map[string]*task.Request)(nil), "scheduler.State.RequestsEntry")
	proto.RegisterMapType((map[string]*Worker)(nil), "scheduler.State.WorkersEntry")
	proto.RegisterType((*Config)(nil), "scheduler.Config")
	proto.RegisterMapType((map[string]*account.Config)(nil), "scheduler.Config.AccountConfigsEntry")
}

func init() {
	proto.RegisterFile("infra/qscheduler/qslib/scheduler/scheduler.proto", fileDescriptor_9c9a368e1d01bf8a)
}

var fileDescriptor_9c9a368e1d01bf8a = []byte{
	// 455 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x7c, 0x92, 0x4f, 0x6f, 0xd3, 0x30,
	0x18, 0xc6, 0x95, 0x96, 0x15, 0xfa, 0x76, 0xed, 0x86, 0x91, 0x50, 0x14, 0x09, 0xa8, 0x0a, 0x13,
	0x3d, 0x4c, 0xce, 0x54, 0x0e, 0xa0, 0xdd, 0xf8, 0x77, 0x01, 0xb1, 0x83, 0x19, 0x70, 0xac, 0x9c,
	0xcc, 0x2d, 0x51, 0x3d, 0xbb, 0xf5, 0x9f, 0xa1, 0x7e, 0x27, 0x3e, 0x17, 0x9f, 0x03, 0xc5, 0x76,
	0xba, 0x44, 0xcb, 0x7a, 0x89, 0x63, 0xfb, 0xf9, 0x3d, 0x7a, 0xdf, 0xf7, 0x31, 0x9c, 0x15, 0x62,
	0xa1, 0x68, 0xba, 0xd1, 0xf9, 0x6f, 0x76, 0x65, 0x39, 0x53, 0xe9, 0x46, 0xf3, 0x22, 0x4b, 0x6f,
	0xf7, 0xbb, 0x3f, 0xbc, 0x56, 0xd2, 0x48, 0xd4, 0xdf, 0x1d, 0x24, 0x2f, 0x96, 0x52, 0x2e, 0x39,
	0x4b, 0xdd, 0x45, 0x66, 0x17, 0xa9, 0x29, 0xae, 0x99, 0x36, 0xf4, 0x7a, 0xed, 0xb5, 0xc9, 0xe9,
	0x3d, 0xee, 0x66, 0xbb, 0x66, 0x3a, 0x35, 0x54, 0xaf, 0xdc, 0x27, 0xa8, 0xcf, 0xf6, 0xaa, 0x6f,
	0x58, 0x6e, 0xa4, 0x0a, 0x4b, 0x20, 0x66, 0x7b, 0x09, 0x9a, 0xe7, 0xd2, 0x0a, 0x53, 0xad, 0x9e,
	0x99, 0x5c, 0x40, 0xef, 0x97, 0x54, 0x2b, 0xa6, 0xd0, 0x53, 0xe8, 0x71, 0x9a, 0x31, 0xae, 0xe3,
	0x68, 0xdc, 0x9d, 0xf6, 0x49, 0xd8, 0xa1, 0x53, 0x38, 0x54, 0x56, 0x88, 0x42, 0x2c, 0xe7, 0x65,
	0x75, 0x71, 0x67, 0x1c, 0x4d, 0x07, 0xb3, 0x3e, 0x76, 0xa5, 0x12, 0x2b, 0xc8, 0x20, 0x5c, 0x5f,
	0x52, 0xbd, 0x9a, 0xfc, 0xeb, 0xc2, 0xc1, 0x77, 0x43, 0x0d, 0x43, 0xe7, 0xf0, 0x48, 0xb1, 0x8d,
	0x65, 0xda, 0x78, 0xc7, 0xc1, 0xec, 0x39, 0xbe, 0x9d, 0x9e, 0xd3, 0x60, 0x12, 0x04, 0x9f, 0x85,
	0x51, 0x5b, 0xb2, 0xd3, 0x97, 0x6c, 0x46, 0x39, 0x15, 0x39, 0xd3, 0x71, 0xe7, 0x1e, 0xf6, 0x43,
	0x10, 0x04, 0xb6, 0xd2, 0xa3, 0xb7, 0xf0, 0xf0, 0x8f, 0xeb, 0x48, 0xc7, 0x5d, 0x87, 0x3e, 0xbb,
	0x83, 0xfa, 0x8e, 0x03, 0x59, 0xa9, 0xd1, 0x27, 0x38, 0xe6, 0x54, 0x9b, 0xb9, 0x5d, 0x5f, 0x51,
	0xc3, 0xe6, 0x65, 0x7a, 0xf1, 0x03, 0xd7, 0x6c, 0x82, 0x7d, 0xb4, 0xb8, 0x8a, 0x16, 0x5f, 0x56,
	0xd1, 0x92, 0x51, 0xc9, 0xfc, 0x70, 0x48, 0x79, 0x98, 0x7c, 0x81, 0x61, 0xa3, 0x2b, 0x74, 0x0c,
	0xdd, 0x15, 0xdb, 0xc6, 0xd1, 0x38, 0x9a, 0xf6, 0x49, 0xf9, 0x8b, 0x5e, 0xc2, 0xc1, 0x0d, 0xe5,
	0x96, 0x85, 0x51, 0x0e, 0xc3, 0x28, 0x3d, 0x45, 0xfc, 0xdd, 0x79, 0xe7, 0x5d, 0x94, 0x7c, 0x85,
	0x61, 0xa3, 0xcb, 0x16, 0xaf, 0x57, 0x4d, 0xaf, 0x11, 0x0e, 0x2f, 0xe2, 0xa7, 0x5b, 0xea, 0x66,
	0xdf, 0xe0, 0xb0, 0xde, 0x77, 0x8b, 0xd7, 0xeb, 0xa6, 0xd7, 0xe3, 0xda, 0xdc, 0x3c, 0x59, 0xb3,
	0x9b, 0xfc, 0x8d, 0xa0, 0xf7, 0x51, 0x8a, 0x45, 0xb1, 0x44, 0x17, 0x70, 0x14, 0x1e, 0xd5, 0x3c,
	0x77, 0x27, 0x55, 0xe0, 0x27, 0x35, 0x07, 0xaf, 0xc5, 0xef, 0xbd, 0xd0, 0xef, 0x42, 0x02, 0x23,
	0xda, 0x38, 0x4c, 0x08, 0x3c, 0x69, 0x91, 0xb5, 0x14, 0x7c, 0xd2, 0x2c, 0xf8, 0x08, 0x57, 0x6f,
	0xdb, 0x73, 0xb5, 0x72, 0xb3, 0x9e, 0x8b, 0xee, 0xcd, 0xff, 0x00, 0x00, 0x00, 0xff, 0xff, 0x4d,
	0x2d, 0x8b, 0xe0, 0xe2, 0x03, 0x00, 0x00,
}
