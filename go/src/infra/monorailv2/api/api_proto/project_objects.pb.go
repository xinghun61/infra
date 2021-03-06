// Code generated by protoc-gen-go. DO NOT EDIT.
// source: api/api_proto/project_objects.proto

package monorail

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

// Next available tag: 4
type Project struct {
	Name                 string   `protobuf:"bytes,1,opt,name=name,proto3" json:"name,omitempty"`
	Summary              string   `protobuf:"bytes,2,opt,name=summary,proto3" json:"summary,omitempty"`
	Description          string   `protobuf:"bytes,3,opt,name=description,proto3" json:"description,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Project) Reset()         { *m = Project{} }
func (m *Project) String() string { return proto.CompactTextString(m) }
func (*Project) ProtoMessage()    {}
func (*Project) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{0}
}

func (m *Project) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Project.Unmarshal(m, b)
}
func (m *Project) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Project.Marshal(b, m, deterministic)
}
func (m *Project) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Project.Merge(m, src)
}
func (m *Project) XXX_Size() int {
	return xxx_messageInfo_Project.Size(m)
}
func (m *Project) XXX_DiscardUnknown() {
	xxx_messageInfo_Project.DiscardUnknown(m)
}

var xxx_messageInfo_Project proto.InternalMessageInfo

func (m *Project) GetName() string {
	if m != nil {
		return m.Name
	}
	return ""
}

func (m *Project) GetSummary() string {
	if m != nil {
		return m.Summary
	}
	return ""
}

func (m *Project) GetDescription() string {
	if m != nil {
		return m.Description
	}
	return ""
}

// Next available tag: 6
type StatusDef struct {
	Status               string   `protobuf:"bytes,1,opt,name=status,proto3" json:"status,omitempty"`
	MeansOpen            bool     `protobuf:"varint,2,opt,name=means_open,json=meansOpen,proto3" json:"means_open,omitempty"`
	Rank                 uint32   `protobuf:"varint,3,opt,name=rank,proto3" json:"rank,omitempty"`
	Docstring            string   `protobuf:"bytes,4,opt,name=docstring,proto3" json:"docstring,omitempty"`
	Deprecated           bool     `protobuf:"varint,5,opt,name=deprecated,proto3" json:"deprecated,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *StatusDef) Reset()         { *m = StatusDef{} }
func (m *StatusDef) String() string { return proto.CompactTextString(m) }
func (*StatusDef) ProtoMessage()    {}
func (*StatusDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{1}
}

func (m *StatusDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_StatusDef.Unmarshal(m, b)
}
func (m *StatusDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_StatusDef.Marshal(b, m, deterministic)
}
func (m *StatusDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_StatusDef.Merge(m, src)
}
func (m *StatusDef) XXX_Size() int {
	return xxx_messageInfo_StatusDef.Size(m)
}
func (m *StatusDef) XXX_DiscardUnknown() {
	xxx_messageInfo_StatusDef.DiscardUnknown(m)
}

var xxx_messageInfo_StatusDef proto.InternalMessageInfo

func (m *StatusDef) GetStatus() string {
	if m != nil {
		return m.Status
	}
	return ""
}

func (m *StatusDef) GetMeansOpen() bool {
	if m != nil {
		return m.MeansOpen
	}
	return false
}

func (m *StatusDef) GetRank() uint32 {
	if m != nil {
		return m.Rank
	}
	return 0
}

func (m *StatusDef) GetDocstring() string {
	if m != nil {
		return m.Docstring
	}
	return ""
}

func (m *StatusDef) GetDeprecated() bool {
	if m != nil {
		return m.Deprecated
	}
	return false
}

// Next available tag: 5
type LabelDef struct {
	Label                string   `protobuf:"bytes,1,opt,name=label,proto3" json:"label,omitempty"`
	Docstring            string   `protobuf:"bytes,3,opt,name=docstring,proto3" json:"docstring,omitempty"`
	Deprecated           bool     `protobuf:"varint,4,opt,name=deprecated,proto3" json:"deprecated,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *LabelDef) Reset()         { *m = LabelDef{} }
func (m *LabelDef) String() string { return proto.CompactTextString(m) }
func (*LabelDef) ProtoMessage()    {}
func (*LabelDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{2}
}

func (m *LabelDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_LabelDef.Unmarshal(m, b)
}
func (m *LabelDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_LabelDef.Marshal(b, m, deterministic)
}
func (m *LabelDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_LabelDef.Merge(m, src)
}
func (m *LabelDef) XXX_Size() int {
	return xxx_messageInfo_LabelDef.Size(m)
}
func (m *LabelDef) XXX_DiscardUnknown() {
	xxx_messageInfo_LabelDef.DiscardUnknown(m)
}

var xxx_messageInfo_LabelDef proto.InternalMessageInfo

func (m *LabelDef) GetLabel() string {
	if m != nil {
		return m.Label
	}
	return ""
}

func (m *LabelDef) GetDocstring() string {
	if m != nil {
		return m.Docstring
	}
	return ""
}

func (m *LabelDef) GetDeprecated() bool {
	if m != nil {
		return m.Deprecated
	}
	return false
}

// Next available tag: 11
type ComponentDef struct {
	Path                 string      `protobuf:"bytes,1,opt,name=path,proto3" json:"path,omitempty"`
	Docstring            string      `protobuf:"bytes,2,opt,name=docstring,proto3" json:"docstring,omitempty"`
	AdminRefs            []*UserRef  `protobuf:"bytes,3,rep,name=admin_refs,json=adminRefs,proto3" json:"admin_refs,omitempty"`
	CcRefs               []*UserRef  `protobuf:"bytes,4,rep,name=cc_refs,json=ccRefs,proto3" json:"cc_refs,omitempty"`
	Deprecated           bool        `protobuf:"varint,5,opt,name=deprecated,proto3" json:"deprecated,omitempty"`
	Created              uint32      `protobuf:"fixed32,6,opt,name=created,proto3" json:"created,omitempty"`
	CreatorRef           *UserRef    `protobuf:"bytes,7,opt,name=creator_ref,json=creatorRef,proto3" json:"creator_ref,omitempty"`
	Modified             uint32      `protobuf:"fixed32,8,opt,name=modified,proto3" json:"modified,omitempty"`
	ModifierRef          *UserRef    `protobuf:"bytes,9,opt,name=modifier_ref,json=modifierRef,proto3" json:"modifier_ref,omitempty"`
	LabelRefs            []*LabelRef `protobuf:"bytes,10,rep,name=label_refs,json=labelRefs,proto3" json:"label_refs,omitempty"`
	XXX_NoUnkeyedLiteral struct{}    `json:"-"`
	XXX_unrecognized     []byte      `json:"-"`
	XXX_sizecache        int32       `json:"-"`
}

func (m *ComponentDef) Reset()         { *m = ComponentDef{} }
func (m *ComponentDef) String() string { return proto.CompactTextString(m) }
func (*ComponentDef) ProtoMessage()    {}
func (*ComponentDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{3}
}

func (m *ComponentDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_ComponentDef.Unmarshal(m, b)
}
func (m *ComponentDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_ComponentDef.Marshal(b, m, deterministic)
}
func (m *ComponentDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_ComponentDef.Merge(m, src)
}
func (m *ComponentDef) XXX_Size() int {
	return xxx_messageInfo_ComponentDef.Size(m)
}
func (m *ComponentDef) XXX_DiscardUnknown() {
	xxx_messageInfo_ComponentDef.DiscardUnknown(m)
}

var xxx_messageInfo_ComponentDef proto.InternalMessageInfo

func (m *ComponentDef) GetPath() string {
	if m != nil {
		return m.Path
	}
	return ""
}

func (m *ComponentDef) GetDocstring() string {
	if m != nil {
		return m.Docstring
	}
	return ""
}

func (m *ComponentDef) GetAdminRefs() []*UserRef {
	if m != nil {
		return m.AdminRefs
	}
	return nil
}

func (m *ComponentDef) GetCcRefs() []*UserRef {
	if m != nil {
		return m.CcRefs
	}
	return nil
}

func (m *ComponentDef) GetDeprecated() bool {
	if m != nil {
		return m.Deprecated
	}
	return false
}

func (m *ComponentDef) GetCreated() uint32 {
	if m != nil {
		return m.Created
	}
	return 0
}

func (m *ComponentDef) GetCreatorRef() *UserRef {
	if m != nil {
		return m.CreatorRef
	}
	return nil
}

func (m *ComponentDef) GetModified() uint32 {
	if m != nil {
		return m.Modified
	}
	return 0
}

func (m *ComponentDef) GetModifierRef() *UserRef {
	if m != nil {
		return m.ModifierRef
	}
	return nil
}

func (m *ComponentDef) GetLabelRefs() []*LabelRef {
	if m != nil {
		return m.LabelRefs
	}
	return nil
}

// Next available tag: 9
type FieldDef struct {
	FieldRef       *FieldRef `protobuf:"bytes,1,opt,name=field_ref,json=fieldRef,proto3" json:"field_ref,omitempty"`
	ApplicableType string    `protobuf:"bytes,2,opt,name=applicable_type,json=applicableType,proto3" json:"applicable_type,omitempty"`
	// TODO(jrobbins): applicable_predicate
	IsRequired    bool       `protobuf:"varint,3,opt,name=is_required,json=isRequired,proto3" json:"is_required,omitempty"`
	IsNiche       bool       `protobuf:"varint,4,opt,name=is_niche,json=isNiche,proto3" json:"is_niche,omitempty"`
	IsMultivalued bool       `protobuf:"varint,5,opt,name=is_multivalued,json=isMultivalued,proto3" json:"is_multivalued,omitempty"`
	Docstring     string     `protobuf:"bytes,6,opt,name=docstring,proto3" json:"docstring,omitempty"`
	AdminRefs     []*UserRef `protobuf:"bytes,7,rep,name=admin_refs,json=adminRefs,proto3" json:"admin_refs,omitempty"`
	// TODO(jrobbins): validation, permission granting, and notification options.
	IsPhaseField         bool        `protobuf:"varint,8,opt,name=is_phase_field,json=isPhaseField,proto3" json:"is_phase_field,omitempty"`
	UserChoices          []*UserRef  `protobuf:"bytes,9,rep,name=user_choices,json=userChoices,proto3" json:"user_choices,omitempty"`
	EnumChoices          []*LabelDef `protobuf:"bytes,10,rep,name=enum_choices,json=enumChoices,proto3" json:"enum_choices,omitempty"`
	XXX_NoUnkeyedLiteral struct{}    `json:"-"`
	XXX_unrecognized     []byte      `json:"-"`
	XXX_sizecache        int32       `json:"-"`
}

func (m *FieldDef) Reset()         { *m = FieldDef{} }
func (m *FieldDef) String() string { return proto.CompactTextString(m) }
func (*FieldDef) ProtoMessage()    {}
func (*FieldDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{4}
}

func (m *FieldDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_FieldDef.Unmarshal(m, b)
}
func (m *FieldDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_FieldDef.Marshal(b, m, deterministic)
}
func (m *FieldDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_FieldDef.Merge(m, src)
}
func (m *FieldDef) XXX_Size() int {
	return xxx_messageInfo_FieldDef.Size(m)
}
func (m *FieldDef) XXX_DiscardUnknown() {
	xxx_messageInfo_FieldDef.DiscardUnknown(m)
}

var xxx_messageInfo_FieldDef proto.InternalMessageInfo

func (m *FieldDef) GetFieldRef() *FieldRef {
	if m != nil {
		return m.FieldRef
	}
	return nil
}

func (m *FieldDef) GetApplicableType() string {
	if m != nil {
		return m.ApplicableType
	}
	return ""
}

func (m *FieldDef) GetIsRequired() bool {
	if m != nil {
		return m.IsRequired
	}
	return false
}

func (m *FieldDef) GetIsNiche() bool {
	if m != nil {
		return m.IsNiche
	}
	return false
}

func (m *FieldDef) GetIsMultivalued() bool {
	if m != nil {
		return m.IsMultivalued
	}
	return false
}

func (m *FieldDef) GetDocstring() string {
	if m != nil {
		return m.Docstring
	}
	return ""
}

func (m *FieldDef) GetAdminRefs() []*UserRef {
	if m != nil {
		return m.AdminRefs
	}
	return nil
}

func (m *FieldDef) GetIsPhaseField() bool {
	if m != nil {
		return m.IsPhaseField
	}
	return false
}

func (m *FieldDef) GetUserChoices() []*UserRef {
	if m != nil {
		return m.UserChoices
	}
	return nil
}

func (m *FieldDef) GetEnumChoices() []*LabelDef {
	if m != nil {
		return m.EnumChoices
	}
	return nil
}

// Next available tag: 3
type FieldOptions struct {
	FieldRef             *FieldRef  `protobuf:"bytes,1,opt,name=field_ref,json=fieldRef,proto3" json:"field_ref,omitempty"`
	UserRefs             []*UserRef `protobuf:"bytes,2,rep,name=user_refs,json=userRefs,proto3" json:"user_refs,omitempty"`
	XXX_NoUnkeyedLiteral struct{}   `json:"-"`
	XXX_unrecognized     []byte     `json:"-"`
	XXX_sizecache        int32      `json:"-"`
}

func (m *FieldOptions) Reset()         { *m = FieldOptions{} }
func (m *FieldOptions) String() string { return proto.CompactTextString(m) }
func (*FieldOptions) ProtoMessage()    {}
func (*FieldOptions) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{5}
}

func (m *FieldOptions) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_FieldOptions.Unmarshal(m, b)
}
func (m *FieldOptions) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_FieldOptions.Marshal(b, m, deterministic)
}
func (m *FieldOptions) XXX_Merge(src proto.Message) {
	xxx_messageInfo_FieldOptions.Merge(m, src)
}
func (m *FieldOptions) XXX_Size() int {
	return xxx_messageInfo_FieldOptions.Size(m)
}
func (m *FieldOptions) XXX_DiscardUnknown() {
	xxx_messageInfo_FieldOptions.DiscardUnknown(m)
}

var xxx_messageInfo_FieldOptions proto.InternalMessageInfo

func (m *FieldOptions) GetFieldRef() *FieldRef {
	if m != nil {
		return m.FieldRef
	}
	return nil
}

func (m *FieldOptions) GetUserRefs() []*UserRef {
	if m != nil {
		return m.UserRefs
	}
	return nil
}

// Next available tag: 4
type ApprovalDef struct {
	FieldRef             *FieldRef  `protobuf:"bytes,1,opt,name=field_ref,json=fieldRef,proto3" json:"field_ref,omitempty"`
	ApproverRefs         []*UserRef `protobuf:"bytes,2,rep,name=approver_refs,json=approverRefs,proto3" json:"approver_refs,omitempty"`
	Survey               string     `protobuf:"bytes,3,opt,name=survey,proto3" json:"survey,omitempty"`
	XXX_NoUnkeyedLiteral struct{}   `json:"-"`
	XXX_unrecognized     []byte     `json:"-"`
	XXX_sizecache        int32      `json:"-"`
}

func (m *ApprovalDef) Reset()         { *m = ApprovalDef{} }
func (m *ApprovalDef) String() string { return proto.CompactTextString(m) }
func (*ApprovalDef) ProtoMessage()    {}
func (*ApprovalDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{6}
}

func (m *ApprovalDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_ApprovalDef.Unmarshal(m, b)
}
func (m *ApprovalDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_ApprovalDef.Marshal(b, m, deterministic)
}
func (m *ApprovalDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_ApprovalDef.Merge(m, src)
}
func (m *ApprovalDef) XXX_Size() int {
	return xxx_messageInfo_ApprovalDef.Size(m)
}
func (m *ApprovalDef) XXX_DiscardUnknown() {
	xxx_messageInfo_ApprovalDef.DiscardUnknown(m)
}

var xxx_messageInfo_ApprovalDef proto.InternalMessageInfo

func (m *ApprovalDef) GetFieldRef() *FieldRef {
	if m != nil {
		return m.FieldRef
	}
	return nil
}

func (m *ApprovalDef) GetApproverRefs() []*UserRef {
	if m != nil {
		return m.ApproverRefs
	}
	return nil
}

func (m *ApprovalDef) GetSurvey() string {
	if m != nil {
		return m.Survey
	}
	return ""
}

// Next available tag: 11
type Config struct {
	ProjectName            string          `protobuf:"bytes,1,opt,name=project_name,json=projectName,proto3" json:"project_name,omitempty"`
	StatusDefs             []*StatusDef    `protobuf:"bytes,2,rep,name=status_defs,json=statusDefs,proto3" json:"status_defs,omitempty"`
	StatusesOfferMerge     []*StatusRef    `protobuf:"bytes,3,rep,name=statuses_offer_merge,json=statusesOfferMerge,proto3" json:"statuses_offer_merge,omitempty"`
	LabelDefs              []*LabelDef     `protobuf:"bytes,4,rep,name=label_defs,json=labelDefs,proto3" json:"label_defs,omitempty"`
	ExclusiveLabelPrefixes []string        `protobuf:"bytes,5,rep,name=exclusive_label_prefixes,json=exclusiveLabelPrefixes,proto3" json:"exclusive_label_prefixes,omitempty"`
	ComponentDefs          []*ComponentDef `protobuf:"bytes,6,rep,name=component_defs,json=componentDefs,proto3" json:"component_defs,omitempty"`
	FieldDefs              []*FieldDef     `protobuf:"bytes,7,rep,name=field_defs,json=fieldDefs,proto3" json:"field_defs,omitempty"`
	ApprovalDefs           []*ApprovalDef  `protobuf:"bytes,8,rep,name=approval_defs,json=approvalDefs,proto3" json:"approval_defs,omitempty"`
	RestrictToKnown        bool            `protobuf:"varint,9,opt,name=restrict_to_known,json=restrictToKnown,proto3" json:"restrict_to_known,omitempty"`
	XXX_NoUnkeyedLiteral   struct{}        `json:"-"`
	XXX_unrecognized       []byte          `json:"-"`
	XXX_sizecache          int32           `json:"-"`
}

func (m *Config) Reset()         { *m = Config{} }
func (m *Config) String() string { return proto.CompactTextString(m) }
func (*Config) ProtoMessage()    {}
func (*Config) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{7}
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

func (m *Config) GetProjectName() string {
	if m != nil {
		return m.ProjectName
	}
	return ""
}

func (m *Config) GetStatusDefs() []*StatusDef {
	if m != nil {
		return m.StatusDefs
	}
	return nil
}

func (m *Config) GetStatusesOfferMerge() []*StatusRef {
	if m != nil {
		return m.StatusesOfferMerge
	}
	return nil
}

func (m *Config) GetLabelDefs() []*LabelDef {
	if m != nil {
		return m.LabelDefs
	}
	return nil
}

func (m *Config) GetExclusiveLabelPrefixes() []string {
	if m != nil {
		return m.ExclusiveLabelPrefixes
	}
	return nil
}

func (m *Config) GetComponentDefs() []*ComponentDef {
	if m != nil {
		return m.ComponentDefs
	}
	return nil
}

func (m *Config) GetFieldDefs() []*FieldDef {
	if m != nil {
		return m.FieldDefs
	}
	return nil
}

func (m *Config) GetApprovalDefs() []*ApprovalDef {
	if m != nil {
		return m.ApprovalDefs
	}
	return nil
}

func (m *Config) GetRestrictToKnown() bool {
	if m != nil {
		return m.RestrictToKnown
	}
	return false
}

// Next available tag: 11
type PresentationConfig struct {
	ProjectThumbnailUrl  string        `protobuf:"bytes,1,opt,name=project_thumbnail_url,json=projectThumbnailUrl,proto3" json:"project_thumbnail_url,omitempty"`
	ProjectSummary       string        `protobuf:"bytes,2,opt,name=project_summary,json=projectSummary,proto3" json:"project_summary,omitempty"`
	CustomIssueEntryUrl  string        `protobuf:"bytes,3,opt,name=custom_issue_entry_url,json=customIssueEntryUrl,proto3" json:"custom_issue_entry_url,omitempty"`
	DefaultQuery         string        `protobuf:"bytes,4,opt,name=default_query,json=defaultQuery,proto3" json:"default_query,omitempty"`
	SavedQueries         []*SavedQuery `protobuf:"bytes,5,rep,name=saved_queries,json=savedQueries,proto3" json:"saved_queries,omitempty"`
	RevisionUrlFormat    string        `protobuf:"bytes,6,opt,name=revision_url_format,json=revisionUrlFormat,proto3" json:"revision_url_format,omitempty"`
	DefaultColSpec       string        `protobuf:"bytes,7,opt,name=default_col_spec,json=defaultColSpec,proto3" json:"default_col_spec,omitempty"`
	DefaultSortSpec      string        `protobuf:"bytes,8,opt,name=default_sort_spec,json=defaultSortSpec,proto3" json:"default_sort_spec,omitempty"`
	DefaultXAttr         string        `protobuf:"bytes,9,opt,name=default_x_attr,json=defaultXAttr,proto3" json:"default_x_attr,omitempty"`
	DefaultYAttr         string        `protobuf:"bytes,10,opt,name=default_y_attr,json=defaultYAttr,proto3" json:"default_y_attr,omitempty"`
	XXX_NoUnkeyedLiteral struct{}      `json:"-"`
	XXX_unrecognized     []byte        `json:"-"`
	XXX_sizecache        int32         `json:"-"`
}

func (m *PresentationConfig) Reset()         { *m = PresentationConfig{} }
func (m *PresentationConfig) String() string { return proto.CompactTextString(m) }
func (*PresentationConfig) ProtoMessage()    {}
func (*PresentationConfig) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{8}
}

func (m *PresentationConfig) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_PresentationConfig.Unmarshal(m, b)
}
func (m *PresentationConfig) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_PresentationConfig.Marshal(b, m, deterministic)
}
func (m *PresentationConfig) XXX_Merge(src proto.Message) {
	xxx_messageInfo_PresentationConfig.Merge(m, src)
}
func (m *PresentationConfig) XXX_Size() int {
	return xxx_messageInfo_PresentationConfig.Size(m)
}
func (m *PresentationConfig) XXX_DiscardUnknown() {
	xxx_messageInfo_PresentationConfig.DiscardUnknown(m)
}

var xxx_messageInfo_PresentationConfig proto.InternalMessageInfo

func (m *PresentationConfig) GetProjectThumbnailUrl() string {
	if m != nil {
		return m.ProjectThumbnailUrl
	}
	return ""
}

func (m *PresentationConfig) GetProjectSummary() string {
	if m != nil {
		return m.ProjectSummary
	}
	return ""
}

func (m *PresentationConfig) GetCustomIssueEntryUrl() string {
	if m != nil {
		return m.CustomIssueEntryUrl
	}
	return ""
}

func (m *PresentationConfig) GetDefaultQuery() string {
	if m != nil {
		return m.DefaultQuery
	}
	return ""
}

func (m *PresentationConfig) GetSavedQueries() []*SavedQuery {
	if m != nil {
		return m.SavedQueries
	}
	return nil
}

func (m *PresentationConfig) GetRevisionUrlFormat() string {
	if m != nil {
		return m.RevisionUrlFormat
	}
	return ""
}

func (m *PresentationConfig) GetDefaultColSpec() string {
	if m != nil {
		return m.DefaultColSpec
	}
	return ""
}

func (m *PresentationConfig) GetDefaultSortSpec() string {
	if m != nil {
		return m.DefaultSortSpec
	}
	return ""
}

func (m *PresentationConfig) GetDefaultXAttr() string {
	if m != nil {
		return m.DefaultXAttr
	}
	return ""
}

func (m *PresentationConfig) GetDefaultYAttr() string {
	if m != nil {
		return m.DefaultYAttr
	}
	return ""
}

// Next available tag: 2
type TemplateDef struct {
	TemplateName         string   `protobuf:"bytes,1,opt,name=template_name,json=templateName,proto3" json:"template_name,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *TemplateDef) Reset()         { *m = TemplateDef{} }
func (m *TemplateDef) String() string { return proto.CompactTextString(m) }
func (*TemplateDef) ProtoMessage()    {}
func (*TemplateDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{9}
}

func (m *TemplateDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_TemplateDef.Unmarshal(m, b)
}
func (m *TemplateDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_TemplateDef.Marshal(b, m, deterministic)
}
func (m *TemplateDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_TemplateDef.Merge(m, src)
}
func (m *TemplateDef) XXX_Size() int {
	return xxx_messageInfo_TemplateDef.Size(m)
}
func (m *TemplateDef) XXX_DiscardUnknown() {
	xxx_messageInfo_TemplateDef.DiscardUnknown(m)
}

var xxx_messageInfo_TemplateDef proto.InternalMessageInfo

func (m *TemplateDef) GetTemplateName() string {
	if m != nil {
		return m.TemplateName
	}
	return ""
}

func init() {
	proto.RegisterType((*Project)(nil), "monorail.Project")
	proto.RegisterType((*StatusDef)(nil), "monorail.StatusDef")
	proto.RegisterType((*LabelDef)(nil), "monorail.LabelDef")
	proto.RegisterType((*ComponentDef)(nil), "monorail.ComponentDef")
	proto.RegisterType((*FieldDef)(nil), "monorail.FieldDef")
	proto.RegisterType((*FieldOptions)(nil), "monorail.FieldOptions")
	proto.RegisterType((*ApprovalDef)(nil), "monorail.ApprovalDef")
	proto.RegisterType((*Config)(nil), "monorail.Config")
	proto.RegisterType((*PresentationConfig)(nil), "monorail.PresentationConfig")
	proto.RegisterType((*TemplateDef)(nil), "monorail.TemplateDef")
}

func init() {
	proto.RegisterFile("api/api_proto/project_objects.proto", fileDescriptor_4f680a8ed8804f88)
}

var fileDescriptor_4f680a8ed8804f88 = []byte{
	// 1093 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x9c, 0x56, 0xdd, 0x6e, 0x1b, 0xc5,
	0x17, 0x97, 0xeb, 0xd4, 0x5e, 0x1f, 0xdb, 0xe9, 0x3f, 0x93, 0x34, 0xda, 0x7f, 0xc4, 0x87, 0x71,
	0x8a, 0x88, 0x7a, 0x91, 0x40, 0x5a, 0x10, 0x20, 0x71, 0x51, 0xa5, 0xad, 0x84, 0xa0, 0x4d, 0xd8,
	0x24, 0x12, 0xbd, 0x61, 0x34, 0xd9, 0x3d, 0x9b, 0x0c, 0xdd, 0xdd, 0xd9, 0xce, 0xcc, 0x9a, 0xf8,
	0x25, 0x90, 0x90, 0x78, 0x0a, 0x9e, 0x88, 0xb7, 0xe0, 0x15, 0xd0, 0x9c, 0x9d, 0xcd, 0xda, 0x6d,
	0xd2, 0x02, 0x57, 0x3e, 0x1f, 0xbf, 0xf3, 0x31, 0xf3, 0x3b, 0x73, 0xd6, 0xb0, 0x2d, 0x4a, 0xb9,
	0x27, 0x4a, 0xc9, 0x4b, 0xad, 0xac, 0xda, 0x2b, 0xb5, 0xfa, 0x19, 0x63, 0xcb, 0xd5, 0x99, 0xfb,
	0x31, 0xbb, 0x64, 0x65, 0x41, 0xae, 0x0a, 0xa5, 0x85, 0xcc, 0xb6, 0xb6, 0x96, 0xe1, 0xb1, 0xca,
	0x73, 0x55, 0xd4, 0xa8, 0xe9, 0x0b, 0xe8, 0x1f, 0xd5, 0xe1, 0x8c, 0xc1, 0x4a, 0x21, 0x72, 0x0c,
	0x3b, 0x93, 0xce, 0xce, 0x20, 0x22, 0x99, 0x85, 0xd0, 0x37, 0x55, 0x9e, 0x0b, 0x3d, 0x0f, 0x6f,
	0x91, 0xb9, 0x51, 0xd9, 0x04, 0x86, 0x09, 0x9a, 0x58, 0xcb, 0xd2, 0x4a, 0x55, 0x84, 0x5d, 0xf2,
	0x2e, 0x9a, 0xa6, 0xbf, 0x77, 0x60, 0x70, 0x6c, 0x85, 0xad, 0xcc, 0x63, 0x4c, 0xd9, 0x26, 0xf4,
	0x0c, 0x29, 0x3e, 0xbf, 0xd7, 0xd8, 0xfb, 0x00, 0x39, 0x8a, 0xc2, 0x70, 0x55, 0x62, 0x41, 0x45,
	0x82, 0x68, 0x40, 0x96, 0xc3, 0x12, 0x0b, 0xd7, 0x94, 0x16, 0xc5, 0x4b, 0xca, 0x3f, 0x8e, 0x48,
	0x66, 0xef, 0xc1, 0x20, 0x51, 0xb1, 0xb1, 0x5a, 0x16, 0xe7, 0xe1, 0x0a, 0x65, 0x6b, 0x0d, 0xec,
	0x03, 0x80, 0x04, 0x4b, 0x8d, 0xb1, 0xb0, 0x98, 0x84, 0xb7, 0x29, 0xe1, 0x82, 0x65, 0xfa, 0x13,
	0x04, 0xdf, 0x8b, 0x33, 0xcc, 0x5c, 0x53, 0x1b, 0x70, 0x3b, 0x73, 0xb2, 0xef, 0xa9, 0x56, 0x96,
	0xf3, 0x77, 0xdf, 0x9e, 0x7f, 0xe5, 0x8d, 0xfc, 0xbf, 0x75, 0x61, 0x74, 0xa0, 0xf2, 0x52, 0x15,
	0x58, 0x58, 0x57, 0x84, 0xc1, 0x4a, 0x29, 0xec, 0x45, 0x73, 0xaf, 0x4e, 0x5e, 0x2e, 0x71, 0xeb,
	0xf5, 0x12, 0x9f, 0x02, 0x88, 0x24, 0x97, 0x05, 0xd7, 0x98, 0x9a, 0xb0, 0x3b, 0xe9, 0xee, 0x0c,
	0xf7, 0xd7, 0x76, 0x1b, 0x3e, 0x77, 0x4f, 0x0d, 0xea, 0x08, 0xd3, 0x68, 0x40, 0xa0, 0x08, 0x53,
	0xc3, 0xee, 0x43, 0x3f, 0x8e, 0x6b, 0xf8, 0xca, 0x4d, 0xf0, 0x5e, 0x1c, 0x13, 0xf6, 0x1d, 0x17,
	0xe4, 0x38, 0x8f, 0x35, 0x92, 0xb3, 0x37, 0xe9, 0xec, 0xf4, 0xa3, 0x46, 0x65, 0xfb, 0x30, 0x24,
	0x51, 0x69, 0x57, 0x2a, 0xec, 0x4f, 0x3a, 0xd7, 0x57, 0x02, 0x8f, 0x8a, 0x30, 0x65, 0x5b, 0x10,
	0xe4, 0x2a, 0x91, 0xa9, 0xc4, 0x24, 0x0c, 0x28, 0xdd, 0x95, 0xce, 0x1e, 0xc2, 0xc8, 0xcb, 0x75,
	0xc2, 0xc1, 0x4d, 0x09, 0x87, 0x0d, 0xcc, 0x65, 0xfc, 0x0c, 0x80, 0x78, 0xaa, 0x8f, 0x0b, 0x74,
	0x5c, 0xd6, 0xc6, 0x10, 0xb9, 0x74, 0x3d, 0x99, 0x97, 0xcc, 0xf4, 0x8f, 0x2e, 0x04, 0x4f, 0x25,
	0x66, 0x89, 0xe3, 0x63, 0x0f, 0x06, 0xa9, 0x93, 0xa9, 0x64, 0x87, 0x4a, 0x2e, 0x84, 0x13, 0xcc,
	0x85, 0x07, 0xa9, 0x97, 0xd8, 0x27, 0x70, 0x47, 0x94, 0x65, 0x26, 0x63, 0x71, 0x96, 0x21, 0xb7,
	0xf3, 0x12, 0x3d, 0x65, 0xab, 0xad, 0xf9, 0x64, 0x5e, 0x22, 0xfb, 0x10, 0x86, 0xd2, 0x70, 0x8d,
	0xaf, 0x2a, 0xa9, 0x31, 0xa1, 0xd1, 0x09, 0x22, 0x90, 0x26, 0xf2, 0x16, 0xf6, 0x7f, 0x08, 0xa4,
	0xe1, 0x85, 0x8c, 0x2f, 0xd0, 0x4f, 0x4e, 0x5f, 0x9a, 0xe7, 0x4e, 0x65, 0x1f, 0xc3, 0xaa, 0x34,
	0x3c, 0xaf, 0x32, 0x2b, 0x67, 0x22, 0xab, 0xae, 0x98, 0x19, 0x4b, 0xf3, 0xac, 0x35, 0x2e, 0x0f,
	0x4e, 0xef, 0xed, 0x83, 0xd3, 0xff, 0x07, 0x83, 0x73, 0x8f, 0xca, 0x96, 0x17, 0xc2, 0x20, 0xa7,
	0x03, 0x13, 0x49, 0x41, 0x34, 0x92, 0xe6, 0xc8, 0x19, 0xe9, 0x3a, 0x1c, 0x51, 0x95, 0x41, 0xcd,
	0xe3, 0x0b, 0x25, 0x63, 0x34, 0xe1, 0xe0, 0xa6, 0xcc, 0x43, 0x07, 0x3b, 0xa8, 0x51, 0xec, 0x73,
	0x18, 0x61, 0x51, 0xe5, 0x57, 0x51, 0xd7, 0x53, 0xf5, 0xd8, 0x85, 0x39, 0x9c, 0x0f, 0x9b, 0x2a,
	0x18, 0x51, 0xd5, 0x43, 0x5a, 0x23, 0xe6, 0xdf, 0xf3, 0xb5, 0x0b, 0x03, 0xea, 0x96, 0x2e, 0xe1,
	0xd6, 0x4d, 0xad, 0x06, 0x55, 0x2d, 0x98, 0xe9, 0xaf, 0x1d, 0x18, 0x3e, 0x2a, 0x4b, 0xad, 0x66,
	0x22, 0xfb, 0x4f, 0x03, 0xf2, 0x05, 0x8c, 0x05, 0xc5, 0xbf, 0xb3, 0xe8, 0xa8, 0xc1, 0xd1, 0xe5,
	0xbb, 0x9d, 0x58, 0xe9, 0x19, 0xce, 0xfd, 0x96, 0xf1, 0xda, 0xf4, 0xaf, 0x2e, 0xf4, 0x0e, 0x54,
	0x91, 0xca, 0x73, 0xf6, 0x11, 0x8c, 0x9a, 0xf5, 0xbe, 0xb0, 0x9c, 0x87, 0xde, 0xf6, 0xdc, 0xed,
	0xe8, 0x87, 0x30, 0xac, 0x77, 0x29, 0x4f, 0xda, 0xda, 0xeb, 0x6d, 0xed, 0xab, 0x1d, 0x1c, 0x81,
	0x69, 0x44, 0xc3, 0x9e, 0xc0, 0x46, 0xad, 0xa1, 0xe1, 0x2a, 0x4d, 0x51, 0xf3, 0x1c, 0xf5, 0x39,
	0xfa, 0x6d, 0xf3, 0x46, 0xb8, 0x6b, 0x9e, 0x35, 0x01, 0x87, 0x0e, 0xff, 0xcc, 0xc1, 0xdb, 0xc7,
	0x98, 0xb4, 0xbb, 0xe7, 0x3a, 0x86, 0xeb, 0xc7, 0x48, 0x95, 0xbf, 0x84, 0x10, 0x2f, 0xe3, 0xac,
	0x32, 0x72, 0x86, 0xbc, 0x0e, 0x2e, 0x35, 0xa6, 0xf2, 0x12, 0x4d, 0x78, 0x7b, 0xd2, 0xdd, 0x19,
	0x44, 0x9b, 0x57, 0x7e, 0x8a, 0x3f, 0xf2, 0x5e, 0xf6, 0x0d, 0xac, 0xc6, 0xcd, 0x66, 0xad, 0x0b,
	0xf6, 0xa8, 0xe0, 0x66, 0x5b, 0x70, 0x71, 0xf3, 0x46, 0xe3, 0x78, 0x41, 0x33, 0xae, 0xd7, 0x9a,
	0xd7, 0xa4, 0x7d, 0x1d, 0xaf, 0x13, 0x4b, 0xbd, 0xa6, 0x5e, 0x32, 0xec, 0xeb, 0x86, 0x59, 0xe1,
	0x4f, 0x18, 0x50, 0xd4, 0xdd, 0x36, 0x6a, 0x61, 0x70, 0x1a, 0x76, 0x45, 0x7d, 0xce, 0xfb, 0xb0,
	0xa6, 0xd1, 0x3d, 0xcc, 0xd8, 0x72, 0xab, 0xf8, 0xcb, 0x42, 0xfd, 0x52, 0xd0, 0x8a, 0x0b, 0xa2,
	0x3b, 0x8d, 0xe3, 0x44, 0x7d, 0xe7, 0xcc, 0xd3, 0x3f, 0xbb, 0xc0, 0x8e, 0x34, 0x1a, 0x2c, 0xac,
	0x70, 0x53, 0xef, 0xd9, 0xdf, 0x87, 0xbb, 0x0d, 0xfb, 0xf6, 0xa2, 0xca, 0xcf, 0x0a, 0x21, 0x33,
	0x5e, 0xe9, 0xe6, 0x7b, 0xb5, 0xee, 0x9d, 0x27, 0x8d, 0xef, 0x54, 0x67, 0x6e, 0x5b, 0x35, 0x31,
	0xcb, 0x9f, 0xee, 0x55, 0x6f, 0x3e, 0xf6, 0x5f, 0xf0, 0x07, 0xb0, 0x19, 0x57, 0xc6, 0xaa, 0x9c,
	0x4b, 0x63, 0x2a, 0xe4, 0x58, 0x58, 0x3d, 0xa7, 0xec, 0xf5, 0x34, 0xae, 0xd7, 0xde, 0x6f, 0x9d,
	0xf3, 0x89, 0xf3, 0xb9, 0xec, 0xdb, 0x30, 0x4e, 0x30, 0x15, 0x55, 0x66, 0xf9, 0xab, 0x0a, 0xf5,
	0xdc, 0x7f, 0x7f, 0x47, 0xde, 0xf8, 0x83, 0xb3, 0xb1, 0xaf, 0x60, 0x6c, 0xc4, 0x0c, 0x13, 0x82,
	0x48, 0x4f, 0xeb, 0x70, 0x7f, 0x63, 0x61, 0xa8, 0x9c, 0x9b, 0xc0, 0xd1, 0xc8, 0x34, 0xb2, 0x44,
	0xc3, 0x76, 0x61, 0x5d, 0xe3, 0x4c, 0x1a, 0xa9, 0x0a, 0xd7, 0x0a, 0x4f, 0x95, 0xce, 0x85, 0xf5,
	0x9b, 0x6e, 0xad, 0x71, 0x9d, 0xea, 0xec, 0x29, 0x39, 0xd8, 0x0e, 0xfc, 0xaf, 0xe9, 0x27, 0x56,
	0x19, 0x37, 0x25, 0xc6, 0xf4, 0x5d, 0x1a, 0x44, 0xab, 0xde, 0x7e, 0xa0, 0xb2, 0xe3, 0x12, 0x63,
	0x47, 0x47, 0x83, 0x34, 0x4a, 0xdb, 0x1a, 0x1a, 0x10, 0xf4, 0x8e, 0x77, 0x1c, 0x2b, 0x6d, 0x09,
	0x7b, 0x0f, 0x9a, 0x68, 0x7e, 0xc9, 0x85, 0xb5, 0x9a, 0x78, 0x6b, 0x8f, 0xf9, 0xe3, 0x23, 0x6b,
	0xf5, 0x22, 0x6a, 0x5e, 0xa3, 0x60, 0x09, 0xf5, 0xc2, 0xa1, 0xa6, 0xfb, 0x30, 0x3c, 0xc1, 0xbc,
	0xcc, 0x84, 0x45, 0xb7, 0x5c, 0xb6, 0x61, 0x6c, 0xbd, 0xba, 0xf8, 0xa2, 0x47, 0x8d, 0xd1, 0x3d,
	0xe9, 0xb3, 0x1e, 0xfd, 0x39, 0x7b, 0xf0, 0x77, 0x00, 0x00, 0x00, 0xff, 0xff, 0x75, 0x94, 0xa3,
	0xa4, 0xe9, 0x09, 0x00, 0x00,
}
