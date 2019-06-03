// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"context"
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func TestAnnouncementsPrelude(t *testing.T) {
	anon := identity.AnonymousIdentity
	someone := identity.Identity("user:chicken@example.com")
	trooper := identity.Identity("user:trooper@example.com")
	state := &authtest.FakeState{
		FakeDB: authtest.FakeDB{
			trooper: {announcementGroup},
		},
	}
	ctx := auth.WithState(context.Background(), state)

	var testCases = []struct {
		methodName string
		caller     identity.Identity
		code       codes.Code
	}{
		{"CreateLiveAnnouncement", anon, codes.Unauthenticated},
		{"CreateLiveAnnouncement", someone, codes.PermissionDenied},
		{"CreateLiveAnnouncement", trooper, 0},
		{"RetireAnnouncement", anon, codes.Unauthenticated},
		{"RetireAnnouncement", someone, codes.PermissionDenied},
		{"RetireAnnouncement", trooper, 0},
		{"UpdateAnnouncementPlatforms", anon, codes.Unauthenticated},
		{"UpdateAnnouncementPlatforms", someone, codes.PermissionDenied},
		{"SearchAnnouncements", anon, 0},
		{"SearchAnnouncements", someone, 0},
	}

	for i, tc := range testCases {
		Convey(fmt.Sprintf("%d - %s by %s", i, tc.methodName, tc.caller), t, func() {
			state.Identity = tc.caller
			_, err := announcementsPrelude(ctx, tc.methodName, nil)
			if tc.code == 0 {
				So(err, ShouldBeNil)
			} else {
				So(status.Code(err), ShouldEqual, tc.code)
			}
		})
	}
	Convey("unrecognized method", t, func() {
		state.Identity = trooper
		So(func() { announcementsPrelude(ctx, "melemele", nil) }, ShouldPanic)
	})
}
