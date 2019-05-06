// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	dashpb "infra/appengine/dashboard/api/dashboard"
	"reflect"
	"testing"
	"time"

	"github.com/golang/protobuf/ptypes/timestamp"
	"go.chromium.org/gae/service/datastore"

	. "github.com/smartystreets/goconvey/convey"
)

func TestConvertAnnouncement(t *testing.T) {
	startTS := int64(764797594)
	endTS := int64(764883994)
	testCases := []struct {
		ann       Announcement
		platforms []*Platform
		expected  *dashpb.Announcement
	}{
		{
			ann: Announcement{
				ID:        1234,
				Retired:   true,
				Message:   "CQ issues",
				Creator:   "trooper",
				StartTime: time.Unix(startTS, 0),
				EndTime:   time.Unix(endTS, 0),
			},
			platforms: []*Platform{
				{Name: "monorail"},
				{
					Name:            "gerrit",
					URLPaths:        []string{"c/infra/infra/*", "src/*"},
					AnnouncementKey: &datastore.Key{},
					ID:              123456,
				},
			},
			expected: &dashpb.Announcement{
				Id:             1234,
				MessageContent: "CQ issues",
				Creator:        "trooper",
				Retired:        true,
				StartTime:      &timestamp.Timestamp{Seconds: startTS},
				EndTime:        &timestamp.Timestamp{Seconds: endTS},
				Platforms: []*dashpb.Platform{
					{Name: "monorail"},
					{
						Name:     "gerrit",
						UrlPaths: []string{"c/infra/infra/*", "src/*"},
					},
				},
			},
		},
		{
			ann: Announcement{
				ID:        13,
				StartTime: time.Unix(startTS, 0),
				EndTime:   time.Unix(endTS, 0),
			},
			expected: &dashpb.Announcement{
				Id:             13,
				MessageContent: "",
				Creator:        "",
				Retired:        false,
				StartTime:      &timestamp.Timestamp{Seconds: startTS},
				EndTime:        &timestamp.Timestamp{Seconds: endTS},
				Platforms:      []*dashpb.Platform{},
			},
		},
	}
	for i, tc := range testCases {
		actual, err := tc.ann.ToProto(tc.platforms)
		if err != nil {
			t.Errorf("%d: unexpected error - %s", i, err)
		}
		if !reflect.DeepEqual(tc.expected, actual) {
			t.Errorf("%d: expected %+v, found %+v", i, tc.expected, actual)
		}
	}
}

func TestCreateLiveAnnouncement(t *testing.T) {
	Convey("CreateLiveAnnouncement", t, func() {
		ctx := newTestContext()
		Convey("successful Announcement creator", func() {
			platforms := []*Platform{
				{
					Name:     "monorail",
					URLPaths: []string{"p/chromium/*"},
				},
				{
					Name:     "som",
					URLPaths: []string{"c/infra/infra/*"},
				},
			}
			ann, err := CreateLiveAnnouncement(
				ctx, "Cow cow cow", "cowman", platforms)
			So(err, ShouldBeNil)
			So(platforms, ShouldHaveLength, 2)
			// Test getting platforms and announcement does not result
			// in error and they were saved correctly in datastore.
			for _, platform := range platforms {
				So(datastore.Get(ctx, platform), ShouldBeNil)
			}
			So(datastore.Get(ctx, ann), ShouldBeNil)
		})
	})
}
