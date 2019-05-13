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
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/sync/parallel"
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
	AnnouncementKey *datastore.Key `gae:"$parent"`
	Name            string         `gae:"$id"`
	URLPaths        []string
}

func (a *Announcement) getPlatforms(c context.Context) ([]*Platform, error) {
	platforms := []*Platform{}
	q := datastore.NewQuery("Platform").Ancestor(datastore.KeyForObj(c, a))
	err := datastore.GetAll(c, q, &platforms)
	return platforms, err
}

// ToProto takes a slice of Platforms that is assumed to belong
// to the Announcement a, and returns a dasphpb.Announcement equivalent.
//
// It returns (aProto, nil) on successful conversion or (nil, err) if there
// was an error while converting timestamps.
func (a *Announcement) ToProto(platforms []*Platform) (*dashpb.Announcement, error) {
	aProto := &dashpb.Announcement{
		Id:             a.ID,
		MessageContent: a.Message,
		Creator:        a.Creator,
		Retired:        a.Retired,
		Platforms:      ConvertPlatforms(platforms),
	}
	endTime, err := ptypes.TimestampProto(a.EndTime)
	if err != nil {
		return nil, fmt.Errorf("error converting announcement EndTime - %s", err)
	}
	aProto.EndTime = endTime

	startTime, err := ptypes.TimestampProto(a.StartTime)
	if err != nil {
		return nil, fmt.Errorf("error converting announcement StartTime - %s", err)
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

// TODO(jojwang): update this to return dashpb.Announcement

// CreateLiveAnnouncement takes announcement information and Platforms to build
// an Announcement and adds AnnouncementKeys to all platforms and puts all
// structs in Datastore.
//
// It returns (announcement, nil) on success, and (nil, err) on datastore errors.
func CreateLiveAnnouncement(c context.Context, message, creator string, platforms []*Platform) (*dashpb.Announcement, error) {
	announcement := &Announcement{
		// datastore will only store timestamps precise to microseconds.
		StartTime: clock.Now(c).UTC().Truncate(time.Microsecond),
		Message:   message,
		Creator:   creator,
	}
	err := datastore.RunInTransaction(c, func(c context.Context) error {
		if err := datastore.Put(c, announcement); err != nil {
			return fmt.Errorf("error writing announcement to datastore - %s", err)
		}

		announcementKey := datastore.NewKey(c, "Announcement", "", announcement.ID, nil)
		for _, platform := range platforms {
			platform.AnnouncementKey = announcementKey
		}

		if err := datastore.Put(c, platforms); err != nil {
			return fmt.Errorf("error writing platforms to datastore - %s", err)
		}
		return nil
	}, nil)
	if err != nil {
		return nil, err
	}
	return announcement.ToProto(platforms)
}

// GetLiveAnnouncements returns dashpb.Announcements that are not retired.
// If a platformName is specified, only live Announcements that are ancestor to the
// platform will be returned. Otherwise, all live Announcements will be returned.
//
// It returns (announcements, nil) on success, and (nil, err) on datastore or conversion errors.
func GetLiveAnnouncements(c context.Context, platformName string) ([]*dashpb.Announcement, error) {
	var liveAnns []*Announcement
	annQ := datastore.NewQuery("Announcement").Eq("Retired", false)
	if err := datastore.GetAll(c, annQ, &liveAnns); err != nil {
		return nil, fmt.Errorf("error getting Announcement entities - %s", err)
	}

	finalAnns := liveAnns
	if platformName != "" {
		finalAnns = make([]*Announcement, 0, len(liveAnns))
		pKeys := make([]*datastore.Key, len(liveAnns))
		for i, ann := range liveAnns {
			pKeys[i] = datastore.NewKey(c, "Platform", platformName, 0, datastore.KeyForObj(c, ann))
		}
		existsR, err := datastore.Exists(c, pKeys)
		if err != nil {
			return nil, fmt.Errorf("error checking for platform existence - %s", err)
		}
		for i, ann := range liveAnns {
			if existsR.Get(0, i) {
				finalAnns = append(finalAnns, ann)
			}
		}
	}
	return GetAllAnnouncementsPlatforms(c, finalAnns)
}

// GetAllAnnouncementsPlatforms takes Announcements that have incomplete or empty
// Platforms, fetches the platforms from datastore, and returns everything in dashpb.Announcements.
//
// It returns (announcements, nil) on success, and (nil, err) on datastore or conversion errors.
func GetAllAnnouncementsPlatforms(c context.Context, announcements []*Announcement) ([]*dashpb.Announcement, error) {
	annProtos := make([]*dashpb.Announcement, len(announcements))
	err := parallel.FanOutIn(func(workC chan<- func() error) {
		for i, ann := range announcements {
			i := i
			ann := ann
			workC <- func() error {
				platforms, err := ann.getPlatforms(c)
				if err != nil {
					return fmt.Errorf("error getting Platform entities -%s", err)
				}
				annProtos[i], err = ann.ToProto(platforms)
				if err != nil {
					return fmt.Errorf("error converting Announcement - %s", err)
				}
				return nil
			}
		}
	})
	if err != nil {
		return nil, err
	}
	return annProtos, nil
}

// TODO(jojwang)
// func GetRetiredAnnouncements(offset int) ([]*dashpb.Announcement, error)
// func RetireAnnouncement(announcementId int64) error
