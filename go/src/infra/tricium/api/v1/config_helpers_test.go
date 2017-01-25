// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/luci-go/common/logging/memlogger"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/authtest"
	"github.com/luci/luci-go/server/auth/identity"
	. "github.com/smartystreets/goconvey/convey"
)

func TestProjectIsKnown(t *testing.T) {
	Convey("Test Environment", t, func() {

		project := "playground/gerrit-tricium"
		sc := &ServiceConfig{
			Projects: []*ProjectDetails{
				{
					Name: project,
				},
			},
		}

		Convey("Known project is known", func() {
			ok := sc.ProjectIsKnown(project)
			So(ok, ShouldBeTrue)
		})

		Convey("Unknown project is unknown", func() {
			ok := sc.ProjectIsKnown("blabla")
			So(ok, ShouldBeFalse)
		})
	})
}

func TestCanRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := memory.Use(memlogger.Use(context.Background()))

		project := "playground/gerrit-tricium"
		okACLGroup := "tricium-playground-requesters"
		okACLUser := "user:ok@example.com"
		pc := &ProjectConfig{
			Name: project,
			Acls: []*Acl{
				{
					Role:  Acl_REQUESTER,
					Group: okACLGroup,
				},
				{
					Role:     Acl_REQUESTER,
					Identity: okACLUser,
				},
			},
		}

		Convey("Only users in OK ACL group can request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity:       "user:abc@example.com",
				IdentityGroups: []string{okACLGroup},
			})
			ok, err := pc.CanRequest(ctx)
			So(err, ShouldBeNil)
			So(ok, ShouldBeTrue)
		})

		Convey("User with OK ACL can request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})
			ok, err := pc.CanRequest(ctx)
			So(err, ShouldBeNil)
			So(ok, ShouldBeTrue)
		})

		Convey("Anonymous users cannot request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.AnonymousIdentity,
			})
			ok, err := pc.CanRequest(ctx)
			So(err, ShouldBeNil)
			So(ok, ShouldBeFalse)
		})
	})
}
