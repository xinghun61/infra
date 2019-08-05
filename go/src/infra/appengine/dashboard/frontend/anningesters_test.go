// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	dashpb "infra/appengine/dashboard/api/dashboard"
	"infra/appengine/dashboard/backend"
	"reflect"
	"testing"
)

func TestIngestPlatforms(t *testing.T) {
	testCases := []struct {
		platforms []*dashpb.Platform
		expected  []*backend.Platform
	}{
		{
			platforms: []*dashpb.Platform{},
			expected:  []*backend.Platform{},
		},
		{
			platforms: []*dashpb.Platform{
				{
					Name:     "monorail",
					UrlPaths: []string{"p/chromium/*", "p/monorail/*"},
				},
				{Name: "som"},
			},
			expected: []*backend.Platform{
				{
					Name:     "monorail",
					URLPaths: []string{"p/chromium/*", "p/monorail/*"},
				},
				{Name: "som"},
			},
		},
	}
	for i, tc := range testCases {
		actual := IngestPlatforms(tc.platforms)
		if !reflect.DeepEqual(actual, tc.expected) {
			t.Errorf("%d: expected %+v, found %+v", i, tc.expected, actual)
		}
	}
}
