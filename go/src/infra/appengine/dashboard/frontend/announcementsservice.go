// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"fmt"
	dashpb "infra/appengine/dashboard/api/dashboard"
	"infra/appengine/dashboard/backend"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// TODO(jojwang): change this to some trooper/chops team level auth group.
const announcementGroup = "chopsdash-access"

var perMethodACL = map[string]string{
	"CreateLiveAnnouncement":      announcementGroup,
	"RetireAnnouncement":          announcementGroup,
	"UpdateAnnouncementPlatforms": announcementGroup,
	"SearchAnnouncements":         "*",
}

func announcementsPrelude(ctx context.Context, methodName string, _req proto.Message) (context.Context, error) {
	// TODO(jojwang): check platform names are valid
	acl, ok := perMethodACL[methodName]
	if !ok {
		panic(fmt.Sprintf("method %q is not defined in perMethodACL", methodName))
	}
	if acl != "*" {
		userIdentity := auth.CurrentIdentity(ctx)
		if userIdentity == identity.AnonymousIdentity {
			return nil, status.Error(codes.Unauthenticated, "user is not logged in")
		}
		hasPerms, err := auth.IsMember(ctx, acl)
		if err != nil {
			return nil, status.Errorf(codes.Internal, "failed to determine membership status - %s", err)
		}
		if !hasPerms {
			return nil, status.Error(codes.PermissionDenied, "caller is not allowed to create announcements")
		}
	}
	return ctx, nil
}

type announcementsServiceImpl struct{}

func (s *announcementsServiceImpl) CreateLiveAnnouncement(ctx context.Context, req *dashpb.CreateLiveAnnouncementRequest) (*dashpb.CreateLiveAnnouncementResponse, error) {
	if len(req.Platforms) == 0 {
		return nil, status.Error(codes.InvalidArgument, "no platforms specified")
	}
	ingestedPlatforms := IngestPlatforms(req.Platforms)
	userIdentity := auth.CurrentIdentity(ctx)
	announcement, err := backend.CreateLiveAnnouncement(ctx, req.MessageContent, string(userIdentity), ingestedPlatforms)
	if err != nil {
		return nil, status.Errorf(
			codes.Internal, "error storing Announcement to datastore - %s", err)
	}
	return &dashpb.CreateLiveAnnouncementResponse{
		Announcement: announcement,
	}, nil
}

func (s *announcementsServiceImpl) RetireAnnouncement(ctx context.Context, req *dashpb.RetireAnnouncementRequest) (*dashpb.Announcement, error) {
	if req.AnnouncementId == 0 {
		return nil, status.Error(codes.InvalidArgument, "Id field was empty")
	}
	err := backend.RetireAnnouncement(ctx, req.AnnouncementId)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error retiring announcement - %s", err)
	}
	ann, err := backend.ListAnnouncements(ctx, req.AnnouncementId)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error getting updated announcement - %s", err)
	}
	return ann[0], nil
}

func (s *announcementsServiceImpl) SearchAnnouncements(ctx context.Context, req *dashpb.SearchAnnouncementsRequest) (*dashpb.SearchAnnouncementsResponse, error) {
	// If Limit is 0, set to -1 so it is ignored and no limit is applied.
	if req.Limit == 0 {
		req.Limit = -1
	}
	anns, err := backend.SearchAnnouncements(ctx, req.PlatformName, req.Retired, req.Limit, req.Offset)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "error getting announcements - %s", err)
	}
	return &dashpb.SearchAnnouncementsResponse{Announcements: anns}, nil
}
