// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	dashpb "infra/appengine/dashboard/api/dashboard"
	"infra/appengine/dashboard/backend"
)

// IngestPlatforms takes a slice of dashpb.Platforms and returns equivalent backend Platforms.
func IngestPlatforms(platforms []*dashpb.Platform) (ingestedPlatforms []*backend.Platform) {
	ingestedPlatforms = make([]*backend.Platform, len(platforms))
	for i, platform := range platforms {
		ingestedPlatforms[i] = &backend.Platform{
			Name:     platform.Name,
			URLPaths: platform.UrlPaths,
		}
	}
	return
}
