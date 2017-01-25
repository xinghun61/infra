// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"fmt"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/server/auth"
)

// ProjectIsKnown checks if the provided project is known to the Tricium service.
func (sc *ServiceConfig) ProjectIsKnown(project string) bool {
	for _, p := range sc.Projects {
		if p.Name == project {
			return true
		}
	}
	return false
}

// CanRequest checks the current user can make service requests for the project.
func (pc *ProjectConfig) CanRequest(c context.Context) (bool, error) {
	return pc.checkAcls(c, Acl_REQUESTER)
}

// CanRead checks the current user can read project results.
func (pc *ProjectConfig) CanRead(c context.Context) (bool, error) {
	return pc.checkAcls(c, Acl_READER)
}

func (pc *ProjectConfig) checkAcls(c context.Context, role Acl_Role) (bool, error) {
	var groups []string
	for _, acl := range pc.Acls {
		if acl.Role != role {
			continue
		}
		if acl.Group != "" {
			groups = append(groups, acl.Group)
		}
		if acl.Identity == string(auth.CurrentIdentity(c)) {
			return true, nil
		}
	}
	ok, err := auth.IsMember(c, groups...)
	if err != nil {
		return false, fmt.Errorf("failed to check member in group(s): %v", err)
	}
	return ok, nil
}
