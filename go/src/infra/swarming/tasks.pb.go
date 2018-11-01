// Code generated by protoc-gen-go. DO NOT EDIT.
// source: tasks.proto

package swarming

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

// TaskState represents the different allowed states for a Task.
//
// This is taken from swarming_rpcs.py:TaskState
type TaskState int32

const (
	// Invalid state, do not use.
	TaskState_INVALID TaskState = 0
	// The task is currently running. This is in fact 3 phases: the initial
	// overhead to fetch input files, the actual task running, and the tear down
	// overhead to archive output files to the server.
	TaskState_RUNNING TaskState = 16
	// The task is currently pending. This means that no bot reaped the task. It
	// will stay in this state until either a task reaps it or the expiration
	// elapsed. The task pending expiration is specified as
	// TaskSlice.expiration_secs, one per task slice.
	TaskState_PENDING TaskState = 32
	// The task is not pending anymore, and never ran due to lack of capacity. This
	// means that other higher priority tasks ran instead and that not enough bots
	// were available to run this task for TaskSlice.expiration_secs seconds.
	TaskState_EXPIRED TaskState = 48
	// The task ran for longer than the allowed time in
	// TaskProperties.execution_timeout_secs or TaskProperties.io_timeout_secs.
	// This means the bot forcefully killed the task process as described in the
	// graceful termination dance in the documentation.
	TaskState_TIMED_OUT TaskState = 64
	// The task ran but the bot had an internal failure, unrelated to the task
	// itself. It can be due to the server being unavailable to get task update,
	// the host on which the bot is running crashing or rebooting, etc.
	TaskState_BOT_DIED TaskState = 80
	// The task never ran, and was manually cancelled via the 'cancel' API before
	// it was reaped.
	TaskState_CANCELED TaskState = 96
	// The task ran and completed normally. The task process exit code may be 0 or
	// another value.
	TaskState_COMPLETED TaskState = 112
	// The task ran but was manually killed via the 'cancel' API. This means the
	// bot forcefully killed the task process as described in the graceful
	// termination dance in the documentation.
	TaskState_KILLED TaskState = 128
	// The task was never set to PENDING and was immediately refused, as the server
	// determined that there is no bot capacity to run this task. This happens
	// because no bot exposes a superset of the requested task dimensions.
	//
	// Set TaskSlice.wait_for_capacity to True to force the server to keep the task
	// slice pending even in this case. Generally speaking, the task will
	// eventually switch to EXPIRED, as there's no bot to run it. That said, there
	// are situations where it is known that in some not-too-distant future a wild
	// bot will appear that will be able to run this task.
	TaskState_NO_RESOURCE TaskState = 256
)

var TaskState_name = map[int32]string{
	0:   "INVALID",
	16:  "RUNNING",
	32:  "PENDING",
	48:  "EXPIRED",
	64:  "TIMED_OUT",
	80:  "BOT_DIED",
	96:  "CANCELED",
	112: "COMPLETED",
	128: "KILLED",
	256: "NO_RESOURCE",
}

var TaskState_value = map[string]int32{
	"INVALID":     0,
	"RUNNING":     16,
	"PENDING":     32,
	"EXPIRED":     48,
	"TIMED_OUT":   64,
	"BOT_DIED":    80,
	"CANCELED":    96,
	"COMPLETED":   112,
	"KILLED":      128,
	"NO_RESOURCE": 256,
}

func (x TaskState) String() string {
	return proto.EnumName(TaskState_name, int32(x))
}

func (TaskState) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_b3834c8ef8464a3f, []int{0}
}

func init() {
	proto.RegisterEnum("swarming.TaskState", TaskState_name, TaskState_value)
}

func init() { proto.RegisterFile("tasks.proto", fileDescriptor_b3834c8ef8464a3f) }

var fileDescriptor_b3834c8ef8464a3f = []byte{
	// 188 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x1c, 0xce, 0x41, 0x4a, 0xc4, 0x30,
	0x14, 0xc6, 0x71, 0xeb, 0xa2, 0xb6, 0x89, 0xc2, 0x23, 0x27, 0x70, 0xed, 0x42, 0x04, 0x2f, 0x60,
	0xcd, 0x7b, 0x48, 0x30, 0x4d, 0x42, 0x9a, 0x8a, 0xbb, 0x1a, 0x41, 0x44, 0x8a, 0xd3, 0xd2, 0x04,
	0x66, 0xdb, 0x63, 0xcc, 0x71, 0x87, 0xcc, 0xf2, 0xc7, 0xf7, 0x2d, 0xfe, 0x8c, 0xe7, 0x98, 0xe6,
	0xf4, 0xb8, 0x6e, 0x4b, 0x5e, 0x44, 0x93, 0x8e, 0x71, 0xfb, 0xff, 0x3b, 0xfc, 0x3e, 0x9c, 0x2a,
	0xd6, 0x86, 0x98, 0xe6, 0x21, 0xc7, 0xfc, 0x23, 0x38, 0xbb, 0x51, 0xe6, 0xa3, 0xd3, 0x0a, 0xe1,
	0xaa, 0xc0, 0x8f, 0xc6, 0x28, 0xf3, 0x06, 0x50, 0xe0, 0xc8, 0x60, 0xc1, 0x7d, 0x01, 0x7d, 0x3a,
	0xe5, 0x09, 0xe1, 0x49, 0xdc, 0xb1, 0x36, 0xa8, 0x9e, 0x70, 0xb2, 0x63, 0x80, 0x17, 0x71, 0xcb,
	0x9a, 0x57, 0x1b, 0x26, 0x54, 0x84, 0xe0, 0x8a, 0x64, 0x67, 0x24, 0x69, 0x42, 0xf8, 0x2a, 0x57,
	0x69, 0x7b, 0xa7, 0x29, 0x10, 0xc2, 0x2a, 0x38, 0xab, 0xdf, 0x95, 0x2e, 0xd3, 0x5e, 0x09, 0x60,
	0xdc, 0xd8, 0xc9, 0xd3, 0x60, 0x47, 0x2f, 0x09, 0xf6, 0xeb, 0xef, 0xfa, 0xd2, 0xfa, 0x7c, 0x0e,
	0x00, 0x00, 0xff, 0xff, 0x53, 0x39, 0xa7, 0xc5, 0xba, 0x00, 0x00, 0x00,
}
