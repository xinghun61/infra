// Code generated by MockGen. DO NOT EDIT.
// Source: tasker.pb.go

// Package fleet is a generated GoMock package.
package fleet

import (
	context "context"
	gomock "github.com/golang/mock/gomock"
	grpc "google.golang.org/grpc"
	reflect "reflect"
)

// MockTaskerClient is a mock of TaskerClient interface
type MockTaskerClient struct {
	ctrl     *gomock.Controller
	recorder *MockTaskerClientMockRecorder
}

// MockTaskerClientMockRecorder is the mock recorder for MockTaskerClient
type MockTaskerClientMockRecorder struct {
	mock *MockTaskerClient
}

// NewMockTaskerClient creates a new mock instance
func NewMockTaskerClient(ctrl *gomock.Controller) *MockTaskerClient {
	mock := &MockTaskerClient{ctrl: ctrl}
	mock.recorder = &MockTaskerClientMockRecorder{mock}
	return mock
}

// EXPECT returns an object that allows the caller to indicate expected use
func (m *MockTaskerClient) EXPECT() *MockTaskerClientMockRecorder {
	return m.recorder
}

// TriggerRepairOnIdle mocks base method
func (m *MockTaskerClient) TriggerRepairOnIdle(ctx context.Context, in *TriggerRepairOnIdleRequest, opts ...grpc.CallOption) (*TaskerTasksResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "TriggerRepairOnIdle", varargs...)
	ret0, _ := ret[0].(*TaskerTasksResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// TriggerRepairOnIdle indicates an expected call of TriggerRepairOnIdle
func (mr *MockTaskerClientMockRecorder) TriggerRepairOnIdle(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "TriggerRepairOnIdle", reflect.TypeOf((*MockTaskerClient)(nil).TriggerRepairOnIdle), varargs...)
}

// TriggerRepairOnRepairFailed mocks base method
func (m *MockTaskerClient) TriggerRepairOnRepairFailed(ctx context.Context, in *TriggerRepairOnRepairFailedRequest, opts ...grpc.CallOption) (*TaskerTasksResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "TriggerRepairOnRepairFailed", varargs...)
	ret0, _ := ret[0].(*TaskerTasksResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// TriggerRepairOnRepairFailed indicates an expected call of TriggerRepairOnRepairFailed
func (mr *MockTaskerClientMockRecorder) TriggerRepairOnRepairFailed(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "TriggerRepairOnRepairFailed", reflect.TypeOf((*MockTaskerClient)(nil).TriggerRepairOnRepairFailed), varargs...)
}

// EnsureBackgroundTasks mocks base method
func (m *MockTaskerClient) EnsureBackgroundTasks(ctx context.Context, in *EnsureBackgroundTasksRequest, opts ...grpc.CallOption) (*TaskerTasksResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "EnsureBackgroundTasks", varargs...)
	ret0, _ := ret[0].(*TaskerTasksResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// EnsureBackgroundTasks indicates an expected call of EnsureBackgroundTasks
func (mr *MockTaskerClientMockRecorder) EnsureBackgroundTasks(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "EnsureBackgroundTasks", reflect.TypeOf((*MockTaskerClient)(nil).EnsureBackgroundTasks), varargs...)
}

// MockTaskerServer is a mock of TaskerServer interface
type MockTaskerServer struct {
	ctrl     *gomock.Controller
	recorder *MockTaskerServerMockRecorder
}

// MockTaskerServerMockRecorder is the mock recorder for MockTaskerServer
type MockTaskerServerMockRecorder struct {
	mock *MockTaskerServer
}

// NewMockTaskerServer creates a new mock instance
func NewMockTaskerServer(ctrl *gomock.Controller) *MockTaskerServer {
	mock := &MockTaskerServer{ctrl: ctrl}
	mock.recorder = &MockTaskerServerMockRecorder{mock}
	return mock
}

// EXPECT returns an object that allows the caller to indicate expected use
func (m *MockTaskerServer) EXPECT() *MockTaskerServerMockRecorder {
	return m.recorder
}

// TriggerRepairOnIdle mocks base method
func (m *MockTaskerServer) TriggerRepairOnIdle(arg0 context.Context, arg1 *TriggerRepairOnIdleRequest) (*TaskerTasksResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "TriggerRepairOnIdle", arg0, arg1)
	ret0, _ := ret[0].(*TaskerTasksResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// TriggerRepairOnIdle indicates an expected call of TriggerRepairOnIdle
func (mr *MockTaskerServerMockRecorder) TriggerRepairOnIdle(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "TriggerRepairOnIdle", reflect.TypeOf((*MockTaskerServer)(nil).TriggerRepairOnIdle), arg0, arg1)
}

// TriggerRepairOnRepairFailed mocks base method
func (m *MockTaskerServer) TriggerRepairOnRepairFailed(arg0 context.Context, arg1 *TriggerRepairOnRepairFailedRequest) (*TaskerTasksResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "TriggerRepairOnRepairFailed", arg0, arg1)
	ret0, _ := ret[0].(*TaskerTasksResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// TriggerRepairOnRepairFailed indicates an expected call of TriggerRepairOnRepairFailed
func (mr *MockTaskerServerMockRecorder) TriggerRepairOnRepairFailed(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "TriggerRepairOnRepairFailed", reflect.TypeOf((*MockTaskerServer)(nil).TriggerRepairOnRepairFailed), arg0, arg1)
}

// EnsureBackgroundTasks mocks base method
func (m *MockTaskerServer) EnsureBackgroundTasks(arg0 context.Context, arg1 *EnsureBackgroundTasksRequest) (*TaskerTasksResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "EnsureBackgroundTasks", arg0, arg1)
	ret0, _ := ret[0].(*TaskerTasksResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// EnsureBackgroundTasks indicates an expected call of EnsureBackgroundTasks
func (mr *MockTaskerServerMockRecorder) EnsureBackgroundTasks(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "EnsureBackgroundTasks", reflect.TypeOf((*MockTaskerServer)(nil).EnsureBackgroundTasks), arg0, arg1)
}
