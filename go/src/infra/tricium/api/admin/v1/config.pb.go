// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/tricium/api/admin/v1/config.proto

package admin

import prpc "go.chromium.org/luci/grpc/prpc"

import (
	context "context"
	fmt "fmt"
	proto "github.com/golang/protobuf/proto"
	grpc "google.golang.org/grpc"
	codes "google.golang.org/grpc/codes"
	status "google.golang.org/grpc/status"
	v1 "infra/tricium/api/v1"
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

type GenerateWorkflowRequest struct {
	// The project to generate a workflow config for.
	//
	// The project name used must be known to Tricium.
	Project string `protobuf:"bytes,1,opt,name=project,proto3" json:"project,omitempty"`
	// The paths to generate the workflow config.
	//
	// This list of file metadata includes file paths which are used to
	// decide which workers to include in the workflow.
	Files                []*v1.Data_File `protobuf:"bytes,2,rep,name=files,proto3" json:"files,omitempty"`
	XXX_NoUnkeyedLiteral struct{}        `json:"-"`
	XXX_unrecognized     []byte          `json:"-"`
	XXX_sizecache        int32           `json:"-"`
}

func (m *GenerateWorkflowRequest) Reset()         { *m = GenerateWorkflowRequest{} }
func (m *GenerateWorkflowRequest) String() string { return proto.CompactTextString(m) }
func (*GenerateWorkflowRequest) ProtoMessage()    {}
func (*GenerateWorkflowRequest) Descriptor() ([]byte, []int) {
	return fileDescriptor_34ba87ef8c2d46b9, []int{0}
}

func (m *GenerateWorkflowRequest) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_GenerateWorkflowRequest.Unmarshal(m, b)
}
func (m *GenerateWorkflowRequest) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_GenerateWorkflowRequest.Marshal(b, m, deterministic)
}
func (m *GenerateWorkflowRequest) XXX_Merge(src proto.Message) {
	xxx_messageInfo_GenerateWorkflowRequest.Merge(m, src)
}
func (m *GenerateWorkflowRequest) XXX_Size() int {
	return xxx_messageInfo_GenerateWorkflowRequest.Size(m)
}
func (m *GenerateWorkflowRequest) XXX_DiscardUnknown() {
	xxx_messageInfo_GenerateWorkflowRequest.DiscardUnknown(m)
}

var xxx_messageInfo_GenerateWorkflowRequest proto.InternalMessageInfo

func (m *GenerateWorkflowRequest) GetProject() string {
	if m != nil {
		return m.Project
	}
	return ""
}

func (m *GenerateWorkflowRequest) GetFiles() []*v1.Data_File {
	if m != nil {
		return m.Files
	}
	return nil
}

type GenerateWorkflowResponse struct {
	// The generated workflow.
	Workflow             *Workflow `protobuf:"bytes,1,opt,name=workflow,proto3" json:"workflow,omitempty"`
	XXX_NoUnkeyedLiteral struct{}  `json:"-"`
	XXX_unrecognized     []byte    `json:"-"`
	XXX_sizecache        int32     `json:"-"`
}

func (m *GenerateWorkflowResponse) Reset()         { *m = GenerateWorkflowResponse{} }
func (m *GenerateWorkflowResponse) String() string { return proto.CompactTextString(m) }
func (*GenerateWorkflowResponse) ProtoMessage()    {}
func (*GenerateWorkflowResponse) Descriptor() ([]byte, []int) {
	return fileDescriptor_34ba87ef8c2d46b9, []int{1}
}

func (m *GenerateWorkflowResponse) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_GenerateWorkflowResponse.Unmarshal(m, b)
}
func (m *GenerateWorkflowResponse) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_GenerateWorkflowResponse.Marshal(b, m, deterministic)
}
func (m *GenerateWorkflowResponse) XXX_Merge(src proto.Message) {
	xxx_messageInfo_GenerateWorkflowResponse.Merge(m, src)
}
func (m *GenerateWorkflowResponse) XXX_Size() int {
	return xxx_messageInfo_GenerateWorkflowResponse.Size(m)
}
func (m *GenerateWorkflowResponse) XXX_DiscardUnknown() {
	xxx_messageInfo_GenerateWorkflowResponse.DiscardUnknown(m)
}

var xxx_messageInfo_GenerateWorkflowResponse proto.InternalMessageInfo

func (m *GenerateWorkflowResponse) GetWorkflow() *Workflow {
	if m != nil {
		return m.Workflow
	}
	return nil
}

func init() {
	proto.RegisterType((*GenerateWorkflowRequest)(nil), "admin.GenerateWorkflowRequest")
	proto.RegisterType((*GenerateWorkflowResponse)(nil), "admin.GenerateWorkflowResponse")
}

func init() {
	proto.RegisterFile("infra/tricium/api/admin/v1/config.proto", fileDescriptor_34ba87ef8c2d46b9)
}

var fileDescriptor_34ba87ef8c2d46b9 = []byte{
	// 232 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x7c, 0x90, 0xc1, 0x4e, 0x02, 0x31,
	0x10, 0x86, 0x83, 0x06, 0xd4, 0xe1, 0xa0, 0xe9, 0xc5, 0x66, 0x0f, 0x42, 0xb8, 0xb8, 0xc6, 0xa4,
	0x0d, 0xeb, 0x23, 0x68, 0xe4, 0xbe, 0x1e, 0x3c, 0x71, 0xa8, 0xcb, 0xd4, 0x8c, 0x2e, 0x6d, 0x6d,
	0x0b, 0xbc, 0xbe, 0xb1, 0x5d, 0x38, 0x48, 0x96, 0x63, 0xdb, 0xef, 0xff, 0x3a, 0xf3, 0xc3, 0x3d,
	0x19, 0xed, 0x95, 0x8c, 0x9e, 0x1a, 0xda, 0xac, 0xa5, 0x72, 0x24, 0xd5, 0x6a, 0x4d, 0x46, 0x6e,
	0xe7, 0xb2, 0xb1, 0x46, 0xd3, 0xa7, 0x70, 0xde, 0x46, 0xcb, 0x86, 0xe9, 0xba, 0x78, 0x38, 0xc1,
	0xef, 0xac, 0xff, 0xd6, 0xad, 0xdd, 0xe5, 0x44, 0x31, 0x39, 0x46, 0xb7, 0x73, 0xb9, 0x52, 0x51,
	0x65, 0x60, 0xb6, 0x84, 0xdb, 0x05, 0x1a, 0xf4, 0x2a, 0xe2, 0x7b, 0x17, 0xad, 0xf1, 0x67, 0x83,
	0x21, 0x32, 0x0e, 0x17, 0xce, 0xdb, 0x2f, 0x6c, 0x22, 0x1f, 0x4c, 0x07, 0xe5, 0x55, 0xbd, 0x3f,
	0xb2, 0x12, 0x86, 0x9a, 0x5a, 0x0c, 0xfc, 0x6c, 0x7a, 0x5e, 0x8e, 0x2b, 0x26, 0x3a, 0xbf, 0x78,
	0xf9, 0x13, 0xbf, 0x52, 0x8b, 0x75, 0x06, 0x66, 0x0b, 0xe0, 0xc7, 0xfa, 0xe0, 0xac, 0x09, 0xc8,
	0x1e, 0xe1, 0x72, 0x3f, 0x6d, 0xfa, 0x60, 0x5c, 0x5d, 0x8b, 0xb4, 0x87, 0x38, 0xa0, 0x07, 0xa0,
	0x5a, 0xc2, 0xe8, 0x39, 0x55, 0xc1, 0xde, 0xe0, 0xe6, 0xbf, 0x92, 0xdd, 0x75, 0xc1, 0x9e, 0x55,
	0x8a, 0x49, 0xef, 0x7b, 0x9e, 0xe5, 0x63, 0x94, 0xda, 0x78, 0xfa, 0x0d, 0x00, 0x00, 0xff, 0xff,
	0x59, 0x90, 0x24, 0x63, 0x8b, 0x01, 0x00, 0x00,
}

// Reference imports to suppress errors if they are not otherwise used.
var _ context.Context
var _ grpc.ClientConn

// This is a compile-time assertion to ensure that this generated file
// is compatible with the grpc package it is being compiled against.
const _ = grpc.SupportPackageIsVersion4

// ConfigClient is the client API for Config service.
//
// For semantics around ctx use and closing/ending streaming RPCs, please refer to https://godoc.org/google.golang.org/grpc#ClientConn.NewStream.
type ConfigClient interface {
	// Generates a workflow -- decides which Tricium functions to run.
	//
	// The Tricium config to generate for is specified by the project and list of
	// files in the request.
	//
	// GenerateWorkflow is in "Config" just because generating a workflow
	// requires a valid project config and service config combination.
	// TODO(qyearsley) Move this into launcher or somewhere else more appropriate.
	GenerateWorkflow(ctx context.Context, in *GenerateWorkflowRequest, opts ...grpc.CallOption) (*GenerateWorkflowResponse, error)
}
type configPRPCClient struct {
	client *prpc.Client
}

func NewConfigPRPCClient(client *prpc.Client) ConfigClient {
	return &configPRPCClient{client}
}

func (c *configPRPCClient) GenerateWorkflow(ctx context.Context, in *GenerateWorkflowRequest, opts ...grpc.CallOption) (*GenerateWorkflowResponse, error) {
	out := new(GenerateWorkflowResponse)
	err := c.client.Call(ctx, "admin.Config", "GenerateWorkflow", in, out, opts...)
	if err != nil {
		return nil, err
	}
	return out, nil
}

type configClient struct {
	cc *grpc.ClientConn
}

func NewConfigClient(cc *grpc.ClientConn) ConfigClient {
	return &configClient{cc}
}

func (c *configClient) GenerateWorkflow(ctx context.Context, in *GenerateWorkflowRequest, opts ...grpc.CallOption) (*GenerateWorkflowResponse, error) {
	out := new(GenerateWorkflowResponse)
	err := c.cc.Invoke(ctx, "/admin.Config/GenerateWorkflow", in, out, opts...)
	if err != nil {
		return nil, err
	}
	return out, nil
}

// ConfigServer is the server API for Config service.
type ConfigServer interface {
	// Generates a workflow -- decides which Tricium functions to run.
	//
	// The Tricium config to generate for is specified by the project and list of
	// files in the request.
	//
	// GenerateWorkflow is in "Config" just because generating a workflow
	// requires a valid project config and service config combination.
	// TODO(qyearsley) Move this into launcher or somewhere else more appropriate.
	GenerateWorkflow(context.Context, *GenerateWorkflowRequest) (*GenerateWorkflowResponse, error)
}

// UnimplementedConfigServer can be embedded to have forward compatible implementations.
type UnimplementedConfigServer struct {
}

func (*UnimplementedConfigServer) GenerateWorkflow(ctx context.Context, req *GenerateWorkflowRequest) (*GenerateWorkflowResponse, error) {
	return nil, status.Errorf(codes.Unimplemented, "method GenerateWorkflow not implemented")
}

func RegisterConfigServer(s prpc.Registrar, srv ConfigServer) {
	s.RegisterService(&_Config_serviceDesc, srv)
}

func _Config_GenerateWorkflow_Handler(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	in := new(GenerateWorkflowRequest)
	if err := dec(in); err != nil {
		return nil, err
	}
	if interceptor == nil {
		return srv.(ConfigServer).GenerateWorkflow(ctx, in)
	}
	info := &grpc.UnaryServerInfo{
		Server:     srv,
		FullMethod: "/admin.Config/GenerateWorkflow",
	}
	handler := func(ctx context.Context, req interface{}) (interface{}, error) {
		return srv.(ConfigServer).GenerateWorkflow(ctx, req.(*GenerateWorkflowRequest))
	}
	return interceptor(ctx, in, info, handler)
}

var _Config_serviceDesc = grpc.ServiceDesc{
	ServiceName: "admin.Config",
	HandlerType: (*ConfigServer)(nil),
	Methods: []grpc.MethodDesc{
		{
			MethodName: "GenerateWorkflow",
			Handler:    _Config_GenerateWorkflow_Handler,
		},
	},
	Streams:  []grpc.StreamDesc{},
	Metadata: "infra/tricium/api/admin/v1/config.proto",
}
