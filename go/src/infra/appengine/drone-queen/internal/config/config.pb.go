// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/appengine/drone-queen/internal/config/config.proto

package config

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
const _ = proto.ProtoPackageIsVersion3 // please upgrade the proto package

// Config is the configuration data served by luci-config for this app.
type Config struct {
	// AccessGroup is the luci-auth group controlling access to RPC endpoints.
	AccessGroups         *AccessGroups `protobuf:"bytes,1,opt,name=access_groups,json=accessGroups,proto3" json:"access_groups,omitempty"`
	XXX_NoUnkeyedLiteral struct{}      `json:"-"`
	XXX_unrecognized     []byte        `json:"-"`
	XXX_sizecache        int32         `json:"-"`
}

func (m *Config) Reset()         { *m = Config{} }
func (m *Config) String() string { return proto.CompactTextString(m) }
func (*Config) ProtoMessage()    {}
func (*Config) Descriptor() ([]byte, []int) {
	return fileDescriptor_9bcfef40975c8024, []int{0}
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

func (m *Config) GetAccessGroups() *AccessGroups {
	if m != nil {
		return m.AccessGroups
	}
	return nil
}

// AccessGroups holds access group configuration
type AccessGroups struct {
	// drones is the group for calling drone RPCs.
	Drones string `protobuf:"bytes,1,opt,name=drones,proto3" json:"drones,omitempty"`
	// inventory_providers is the group for calling inventory RPCs.
	InventoryProviders   string   `protobuf:"bytes,2,opt,name=inventory_providers,json=inventoryProviders,proto3" json:"inventory_providers,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *AccessGroups) Reset()         { *m = AccessGroups{} }
func (m *AccessGroups) String() string { return proto.CompactTextString(m) }
func (*AccessGroups) ProtoMessage()    {}
func (*AccessGroups) Descriptor() ([]byte, []int) {
	return fileDescriptor_9bcfef40975c8024, []int{1}
}

func (m *AccessGroups) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_AccessGroups.Unmarshal(m, b)
}
func (m *AccessGroups) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_AccessGroups.Marshal(b, m, deterministic)
}
func (m *AccessGroups) XXX_Merge(src proto.Message) {
	xxx_messageInfo_AccessGroups.Merge(m, src)
}
func (m *AccessGroups) XXX_Size() int {
	return xxx_messageInfo_AccessGroups.Size(m)
}
func (m *AccessGroups) XXX_DiscardUnknown() {
	xxx_messageInfo_AccessGroups.DiscardUnknown(m)
}

var xxx_messageInfo_AccessGroups proto.InternalMessageInfo

func (m *AccessGroups) GetDrones() string {
	if m != nil {
		return m.Drones
	}
	return ""
}

func (m *AccessGroups) GetInventoryProviders() string {
	if m != nil {
		return m.InventoryProviders
	}
	return ""
}

func init() {
	proto.RegisterType((*Config)(nil), "drone_queen.config.Config")
	proto.RegisterType((*AccessGroups)(nil), "drone_queen.config.AccessGroups")
}

func init() {
	proto.RegisterFile("infra/appengine/drone-queen/internal/config/config.proto", fileDescriptor_9bcfef40975c8024)
}

var fileDescriptor_9bcfef40975c8024 = []byte{
	// 195 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0xe2, 0xb2, 0xc8, 0xcc, 0x4b, 0x2b,
	0x4a, 0xd4, 0x4f, 0x2c, 0x28, 0x48, 0xcd, 0x4b, 0xcf, 0xcc, 0x4b, 0xd5, 0x4f, 0x29, 0xca, 0xcf,
	0x4b, 0xd5, 0x2d, 0x2c, 0x4d, 0x4d, 0xcd, 0xd3, 0xcf, 0xcc, 0x2b, 0x49, 0x2d, 0xca, 0x4b, 0xcc,
	0xd1, 0x4f, 0xce, 0xcf, 0x4b, 0xcb, 0x4c, 0x87, 0x52, 0x7a, 0x05, 0x45, 0xf9, 0x25, 0xf9, 0x42,
	0x42, 0x60, 0x95, 0xf1, 0x60, 0x95, 0x7a, 0x10, 0x19, 0x25, 0x7f, 0x2e, 0x36, 0x67, 0x30, 0x4b,
	0xc8, 0x95, 0x8b, 0x37, 0x31, 0x39, 0x39, 0xb5, 0xb8, 0x38, 0x3e, 0xbd, 0x28, 0xbf, 0xb4, 0xa0,
	0x58, 0x82, 0x51, 0x81, 0x51, 0x83, 0xdb, 0x48, 0x41, 0x0f, 0x53, 0x97, 0x9e, 0x23, 0x58, 0xa1,
	0x3b, 0x58, 0x5d, 0x10, 0x4f, 0x22, 0x12, 0x4f, 0x29, 0x9c, 0x8b, 0x07, 0x59, 0x56, 0x48, 0x8c,
	0x8b, 0x0d, 0x6c, 0x00, 0xc4, 0x3c, 0xce, 0x20, 0x28, 0x4f, 0x48, 0x9f, 0x4b, 0x38, 0x33, 0xaf,
	0x2c, 0x35, 0xaf, 0x24, 0xbf, 0xa8, 0x32, 0xbe, 0xa0, 0x28, 0xbf, 0x2c, 0x33, 0x25, 0xb5, 0xa8,
	0x58, 0x82, 0x09, 0xac, 0x48, 0x08, 0x2e, 0x15, 0x00, 0x93, 0x71, 0xe2, 0x88, 0x62, 0x83, 0xd8,
	0x9e, 0xc4, 0x06, 0xf6, 0x8e, 0x31, 0x20, 0x00, 0x00, 0xff, 0xff, 0xb6, 0xeb, 0x23, 0xde, 0x0a,
	0x01, 0x00, 0x00,
}