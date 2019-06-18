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
	ID            int64 `gae:"$id"`
	Retired       bool
	StartTime     time.Time
	EndTime       time.Time
	Message       string
	Creator       string
	Closer        string
	PlatformNames []string
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
		Closer:         a.Closer,
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
	announcement.PlatformNames = make([]string, len(platforms))
	for i, p := range platforms {
		announcement.PlatformNames[i] = p.Name
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

// ListAnnouncements returns dashpb.Announcements for all given announcementIDs.
//
// It returns (announcements, nil) on success, and (nil, err) on datastore or conversion errors.
func ListAnnouncements(c context.Context, announcementIDs ...int64) ([]*dashpb.Announcement, error) {
	anns := make([]*Announcement, len(announcementIDs))
	for i, id := range announcementIDs {
		anns[i] = &Announcement{ID: id}
	}
	if err := datastore.Get(c, anns); err != nil {
		return nil, err
	}
	return GetAllAnnouncementsPlatforms(c, anns)
}

// SearchAnnouncements returns dashpb.Announcements.
// If a platformName is specified, only Announcements that are ancestor to the
// platform will be returned.
// If offset or limit are < 0, they will be ignored.
// The returned Announcements will be either all retired, or all not retired.
//
// It returns (announcements, nil) on success, and (nil, err) on datastore or conversion errors.
func SearchAnnouncements(c context.Context, platformName string, retired bool, limit, offset int32) ([]*dashpb.Announcement, error) {
	annQ := datastore.NewQuery("Announcement").Eq("Retired", retired).Limit(limit).Offset(offset).Order("-EndTime", "-StartTime")
	if platformName != "" {
		annQ = annQ.Eq("PlatformNames", platformName)
	}
	var announcements []*Announcement
	if err := datastore.GetAll(c, annQ, &announcements); err != nil {
		return nil, fmt.Errorf("error getting Announcement entities - %s", err)
	}
	return GetAllAnnouncementsPlatforms(c, announcements)
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
					return fmt.Errorf("error getting Platform entities - %s", err)
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

// RetireAnnouncement sets a given announcement's retired to true.
//
// It returns nil on success and err on datastore errors.
func RetireAnnouncement(c context.Context, announcementID int64, closer string) error {
	announcement := &Announcement{ID: announcementID}
	return datastore.RunInTransaction(c, func(c context.Context) error {
		if err := datastore.Get(c, announcement); err != nil {
			return fmt.Errorf("error getting Announcement - %s", err)
		}
		announcement.Retired = true
		// datastore will only store timestamps precise to microseconds.
		announcement.EndTime = clock.Now(c).UTC().Truncate(time.Microsecond)
		announcement.Closer = closer
		if err := datastore.Put(c, announcement); err != nil {
			return fmt.Errorf("error saving Announcement - %s", err)
		}
		return nil
	}, nil)
}
