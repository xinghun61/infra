// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	dashpb "infra/appengine/dashboard/api/dashboard"

	"golang.org/x/net/context"
)

type announcementsService struct{}

func (s *announcementsService) CreateLiveAnnouncement(ctx context.Context, _ *dashpb.CreateLiveAnnouncementRequest) (*dashpb.CreateLiveAnnouncementResponse, error) {
	return &dashpb.CreateLiveAnnouncementResponse{}, nil
}
