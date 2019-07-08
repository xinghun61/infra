// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package monorail

import "fmt"

// AuthScope is OAuth 2.0 auth scope used by Monorail.
const AuthScope = "https://www.googleapis.com/auth/userinfo.email"

// LabelRestrictViewGoogle specifies that an issue must be visible to googlers only.
const LabelRestrictViewGoogle = "Restrict-View-Google"

var errGrpcOptions = fmt.Errorf("options are not supported")

// IssueURL returns a URL to human-consumable HTML page for the issue.
func IssueURL(host, project string, id int32) string {
	return fmt.Sprintf("https://%s/p/%s/issues/detail?id=%d", host, project, id)
}

// Standard issue statuses.
const (
	// Open statuses:

	// Unconrimed means the issue is new, has been not verified or reproduced..
	StatusUnconfirmed = "Unconfirmed"
	// Untriaged means the issue is confirmed, not reviews for priority of assignment.
	StatusUntriaged = "Untriaged"
	// Available means the issue is triaged, but no owner assigned.
	StatusAvailable = "Available"
	// Started means the work in progress..
	StatusStarted = "Started"
	// ExternalDependency means the issue requires action from a third party.
	StatusExternalDependency = "ExternalDependency"

	// Closed statuses

	// Fixed means work completed, needs verification
	StatusFixed = "Fixed"
	// Verified means test or reporter verified that the fix works
	StatusVerified = "Verified"
	// Duplicate means same root cause as another issue
	StatusDuplicate = "Duplicate"
	//  WontFix means cannot reproduce, works as intended, invalid or absolete.
	StatusWontFix = "WontFix"
	// Archived means old issue with no activity.
	StatusArchived = "Archived"
)
