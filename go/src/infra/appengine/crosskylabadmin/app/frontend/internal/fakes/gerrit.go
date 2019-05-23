// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package fakes

import (
	"context"
	"fmt"

	"github.com/golang/protobuf/ptypes/empty"
	"go.chromium.org/luci/common/proto/gerrit"
	"google.golang.org/grpc"
)

// GerritClient is a fake implementation of the gerrit.GerritClient interface.
type GerritClient struct {
	nextNumber int64
	Changes    []*GerritChange
}

// GerritChange captures information about a single gerrit change created via
// GerritClient.CreateChange()
type GerritChange struct {
	gerrit.ChangeInfo
	GerritChangeEdit
	IsSubmitted bool
}

// GerritChangeEdit captures information about a change edit created via
// GerritClient.ChangeEditFileContent on a ChangeEdit.
type GerritChangeEdit struct {
	// Maps file path to new contents of the file.
	Files       map[string]string
	IsPublished bool
	IsAbandoned bool
	Subject     string
}

// GetChange implements the gerrit.GerritClient interface.
func (gc *GerritClient) GetChange(ctx context.Context, in *gerrit.GetChangeRequest, opts ...grpc.CallOption) (*gerrit.ChangeInfo, error) {
	for _, c := range gc.Changes {
		if in.Number == c.Number {
			ret := c.ChangeInfo
			return &ret, nil
		}
	}
	return nil, fmt.Errorf("No change for %+v", in)
}

// CreateChange implements the gerrit.GerritClient interface.
func (gc *GerritClient) CreateChange(ctx context.Context, in *gerrit.CreateChangeRequest, opts ...grpc.CallOption) (*gerrit.ChangeInfo, error) {
	c := &GerritChange{
		ChangeInfo: gerrit.ChangeInfo{
			Number:          gc.nextNumber,
			Project:         in.Project,
			Ref:             in.Ref,
			Status:          gerrit.ChangeInfo_NEW,
			CurrentRevision: "patch_set_1",
		},
	}
	c.GerritChangeEdit.Files = make(map[string]string)
	c.GerritChangeEdit.Subject = in.Subject
	gc.nextNumber++
	gc.Changes = append(gc.Changes, c)

	// return a copy
	ret := c.ChangeInfo
	return &ret, nil
}

// ChangeEditFileContent implements the gerrit.GerritClient interface.
func (gc *GerritClient) ChangeEditFileContent(ctx context.Context, in *gerrit.ChangeEditFileContentRequest, opts ...grpc.CallOption) (*empty.Empty, error) {
	for _, c := range gc.Changes {
		if in.Number == c.Number {
			c.GerritChangeEdit.Files[in.FilePath] = string(in.Content)
			return &empty.Empty{}, nil
		}
	}
	return &empty.Empty{}, fmt.Errorf("No change edit for %+v", in)
}

// ChangeEditPublish implements the gerrit.GerritClient interface.
func (gc *GerritClient) ChangeEditPublish(ctx context.Context, in *gerrit.ChangeEditPublishRequest, opts ...grpc.CallOption) (*empty.Empty, error) {
	for _, c := range gc.Changes {
		if in.Number == c.Number {
			c.GerritChangeEdit.IsPublished = true
			return &empty.Empty{}, nil
		}
	}
	return &empty.Empty{}, fmt.Errorf("No change edit for %+v", in)
}

// SetReview implements the gerrit.GerritClient interface.
func (gc *GerritClient) SetReview(ctx context.Context, in *gerrit.SetReviewRequest, opts ...grpc.CallOption) (*gerrit.ReviewResult, error) {
	// Not needed for tests.
	return &gerrit.ReviewResult{}, nil
}

// SubmitChange implements the gerrit.GerritClient interface.
func (gc *GerritClient) SubmitChange(ctx context.Context, in *gerrit.SubmitChangeRequest, opts ...grpc.CallOption) (*gerrit.ChangeInfo, error) {
	for _, c := range gc.Changes {
		if in.Number == c.Number {
			c.IsSubmitted = true
			c.ChangeInfo.Status = gerrit.ChangeInfo_MERGED
			// return a copy
			ret := c.ChangeInfo
			return &ret, nil
		}
	}
	return nil, fmt.Errorf("No change for %+v", in)
}

// AbandonChange implements the gerrit.GerritClient interface.
func (gc *GerritClient) AbandonChange(ctx context.Context, in *gerrit.AbandonChangeRequest, opts ...grpc.CallOption) (*gerrit.ChangeInfo, error) {
	for _, c := range gc.Changes {
		if in.Number == c.Number {
			c.IsAbandoned = true
			// return a copy
			ret := c.ChangeInfo
			return &ret, nil
		}
	}
	return nil, fmt.Errorf("No change for %+v", in)
}

// GetMergeable implements the gerrit.GerritClient interface.
func (gc *GerritClient) GetMergeable(ctx context.Context, req *gerrit.GetMergeableRequest, opts ...grpc.CallOption) (*gerrit.MergeableInfo, error) {
	return nil, fmt.Errorf("Fake GetMergeable not yet implemented")
}
