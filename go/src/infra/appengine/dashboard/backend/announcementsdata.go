// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"fmt"
	dashpb "infra/appengine/dashboard/api/dashboard"
	"time"

	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/gae/service/datastore"
	"golang.org/x/net/context"
)

// Announcement contains details of an announcement
type Announcement struct {
	ID        int64 `gae:"$id"`
	Retired   bool
	StartTime time.Time
	EndTime   time.Time
	Message   string
	Creator   string
}

// Platform contains information for where and how an ancestor Announcement should be displayed.
type Platform struct {
	ID              int64          `gae:"$id"`
	AnnouncementKey *datastore.Key `gae:"$parent"`
	Name            string
	URLPaths        []string
}

// ToProto takes a slice of Platforms that is assumed to belong
// to the Announcement a, and returns a dasphpb.Announcement equivalent.
//
// It returns (aProto, nil) on successful conversion or (nil, err) if there
// was an error while converting timestamps.
func (a *Announcement) ToProto(ctx context.Context, platforms []*Platform) (*dashpb.Announcement, error) {
	aProto := &dashpb.Announcement{
		Id:             a.ID,
		MessageContent: a.Message,
		Creator:        a.Creator,
		Retired:        a.Retired,
		Platforms:      ConvertPlatforms(platforms),
	}
	endTime, err := ptypes.TimestampProto(a.EndTime)
	if err != nil {
		return nil, fmt.Errorf("invalid time for EndTime - %s", err)
	}
	aProto.EndTime = endTime

	startTime, err := ptypes.TimestampProto(a.StartTime)
	if err != nil {
		return nil, fmt.Errorf("invalid time for StartTime - %s", err)
	}
	aProto.StartTime = startTime

	return aProto, nil

}

// ToProto returns a dasphpb.Platforms equivalent.
func (p *Platform) ToProto() *dashpb.Platform {
	return &dashpb.Platform{
		Name:     p.Name,
		UrlPaths: p.URLPaths,
	}
}

// ConvertPlatforms takes a slice of Platforms and returns equivalent dasphpb.Platforms.
func ConvertPlatforms(platforms []*Platform) (convertedPlatforms []*dashpb.Platform) {
	convertedPlatforms = make([]*dashpb.Platform, len(platforms))
	for i, platform := range platforms {
		convertedPlatforms[i] = platform.ToProto()
	}
	return
}

// TODO(jojwang): This file will hold methods that save Announcements and Platforms to datastore.
