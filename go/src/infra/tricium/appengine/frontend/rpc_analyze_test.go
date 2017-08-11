// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"testing"

	tq "go.chromium.org/gae/service/taskqueue"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/auth/identity"

	"golang.org/x/net/context"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	trit "infra/tricium/appengine/common/testing"
)

const (
	project   = "playground/gerrit-tricium"
	okACLUser = "user:ok@example.com"
)

// mockConfigProvider mocks the common.ConfigProvider interface.
type mockConfigProvider struct {
}

func (*mockConfigProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	return &tricium.ServiceConfig{
		Projects: []*tricium.ProjectDetails{
			{
				Name: project,
				RepoDetails: &tricium.RepoDetails{
					Kind: tricium.RepoDetails_GIT,
					GitDetails: &tricium.GitRepoDetails{
						Repository: "https://chromium.googlesource.com/playground/gerrit-tricium",
						Ref:        "master",
					},
				},
			},
		},
	}, nil
}
func (*mockConfigProvider) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	return &tricium.ProjectConfig{
		Name: project,
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

func TestAnalyze(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		gitref := "ref/test"
		paths := []string{
			"README.md",
			"README2.md",
		}

		Convey("Service request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})

			_, _, err := analyzeWithAuth(ctx, &tricium.AnalyzeRequest{
				Project: project,
				GitRef:  gitref,
				Paths:   paths,
			}, &mockConfigProvider{})
			So(err, ShouldBeNil)

			Convey("Enqueues launch request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.LauncherQueue]), ShouldEqual, 1)
			})

			Convey("Adds tracking of run", func() {
				r, err := requests(ctx, &mockConfigProvider{})
				So(err, ShouldBeNil)
				So(len(r), ShouldEqual, 1)
			})
		})
	})
}
