// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"context"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"

	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/track"
	"infra/tricium/appengine/common/triciumtest"
)

const (
	project   = "playground-gerrit-tricium"
	host      = "chromium-review.googlesource.com"
	okACLUser = "user:ok@example.com"
	changeID  = "playground/gerrit-tricium~master~I17e97e23ecf2890bf6b72ffd1d7a3167ed1b0a11"
	revision  = "refs/changes/97/97/1"
)

// mockConfigProvider mocks the common.ConfigProvider interface.
type mockConfigProvider struct {
}

func (*mockConfigProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	return nil, nil // not used in this test
}
func (*mockConfigProvider) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	return &tricium.ProjectConfig{
		Repos: []*tricium.RepoDetails{
			{
				Source: &tricium.RepoDetails_GitRepo{
					GitRepo: &tricium.GitRepo{
						Url: "https://chromium.googlesource.com/playground/gerrit-tricium",
					},
				},
			},
		},
		Acls: []*tricium.Acl{
			{
				Role:     tricium.Acl_READER,
				Identity: okACLUser,
			},
			{
				Role:     tricium.Acl_REQUESTER,
				Identity: okACLUser,
			},
		},
	}, nil
}

func (cp *mockConfigProvider) GetAllProjectConfigs(c context.Context) (map[string]*tricium.ProjectConfig, error) {
	pc, _ := cp.GetProjectConfig(c, project)
	return map[string]*tricium.ProjectConfig{project: pc}, nil
}

func TestAnalyze(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := triciumtest.Context()

		Convey("Basic request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})

			_, err := analyzeWithAuth(ctx, &tricium.AnalyzeRequest{
				Project: project,
				Files: []*tricium.Data_File{
					{
						Path: "README.md",
					},
				},
				Source: &tricium.AnalyzeRequest_GitCommit{
					GitCommit: &tricium.GitCommit{
						Url: "https://chromium.googlesource.com/playground/gerrit-tricium",
						Ref: "refs/heads/master",
					},
				},
			}, &mockConfigProvider{})
			So(err, ShouldBeNil)

			Convey("Enqueues launch request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.LauncherQueue]), ShouldEqual, 1)
			})

			Convey("Adds tracking of run", func() {
				r, err := track.FetchRecentRequests(ctx, &mockConfigProvider{})
				So(err, ShouldBeNil)
				So(len(r), ShouldEqual, 1)
			})
		})
	})
}

func TestValidateAnalyzeRequest(t *testing.T) {
	ctx := triciumtest.Context()
	files := []*tricium.Data_File{
		{
			Path: "README.md",
		},
	}
	url := "https://example.com/notimportant.git"

	Convey("A request for a Gerrit change with no host is invalid", t, func() {
		err := validateAnalyzeRequest(ctx, &tricium.AnalyzeRequest{
			Project: project,
			Files:   files,
			Source: &tricium.AnalyzeRequest_GerritRevision{
				GerritRevision: &tricium.GerritRevision{
					// Host field is missing.
					Project: project,
					Change:  changeID,
					GitUrl:  url,
					GitRef:  revision,
				},
			},
		})
		So(err, ShouldNotBeNil)
	})

	Convey("A request with all Gerrit details is valid", t, func() {
		err := validateAnalyzeRequest(ctx, &tricium.AnalyzeRequest{
			Project: project,
			Files:   files,
			Source: &tricium.AnalyzeRequest_GerritRevision{
				GerritRevision: &tricium.GerritRevision{
					Host:    host,
					Project: project,
					Change:  changeID,
					GitUrl:  url,
					GitRef:  revision,
				},
			},
		})
		So(err, ShouldBeNil)
	})

	Convey("A request with an invalid Change ID format is invalid", t, func() {
		err := validateAnalyzeRequest(ctx, &tricium.AnalyzeRequest{
			Project: project,
			Files:   files,
			Source: &tricium.AnalyzeRequest_GerritRevision{
				GerritRevision: &tricium.GerritRevision{
					Host:    host,
					Project: project,
					Change:  "bogus change ID",
					GitUrl:  url,
					GitRef:  revision,
				},
			},
		})
		So(err, ShouldNotBeNil)
	})

	Convey("A request for a Gerrit change with no git URL is invalid", t, func() {
		err := validateAnalyzeRequest(ctx, &tricium.AnalyzeRequest{
			Project: project,
			Files:   files,
			Source: &tricium.AnalyzeRequest_GerritRevision{
				GerritRevision: &tricium.GerritRevision{
					Host:    host,
					Project: project,
					Change:  changeID,
					GitRef:  revision,
				},
			},
		})
		So(err, ShouldNotBeNil)
	})

	Convey("A request for a git commit with all fields is valid", t, func() {
		err := validateAnalyzeRequest(ctx, &tricium.AnalyzeRequest{
			Project: project,
			Files:   files,
			Source: &tricium.AnalyzeRequest_GitCommit{
				GitCommit: &tricium.GitCommit{
					Url: "https://example.com/repo.git",
					Ref: "refs/heads/master",
				},
			},
		})
		So(err, ShouldBeNil)
	})

	Convey("A request for a git commit with no URL is invalid", t, func() {
		err := validateAnalyzeRequest(ctx, &tricium.AnalyzeRequest{
			Project: project,
			Files:   files,
			Source: &tricium.AnalyzeRequest_GitCommit{
				GitCommit: &tricium.GitCommit{
					Ref: "refs/heads/master",
				},
			},
		})
		So(err, ShouldNotBeNil)
	})

	Convey("A request for a git commit with no ref is invalid", t, func() {
		err := validateAnalyzeRequest(ctx, &tricium.AnalyzeRequest{
			Project: project,
			Files:   files,
			Source: &tricium.AnalyzeRequest_GitCommit{
				GitCommit: &tricium.GitCommit{
					Url: "https://example.com/repo.git",
				},
			},
		})
		So(err, ShouldNotBeNil)
	})
}
