// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"golang.org/x/net/context"

	"infra/tricium/appengine/common/track"
)

// GerritAPI specifies the Gerrit service API tuned to the needs of Tricium.
type GerritAPI interface {
	// PostReviewMessage posts a review message to a change.
	PostReviewMessage(c context.Context, host, ref, message string) error
	// PostRobotComments posts robot comments to a change.
	PostRobotComments(c context.Context, host, ref string, comments []*track.Comment) error
}

// GerritServer implements the GerritAPI for the Gerrit service.
var GerritServer gerritServer

type gerritServer struct {
}

// PostReviewMessage implements the GerritAPI.
func (s gerritServer) PostReviewMessage(c context.Context, host, ref, message string) error {
	// TODO(emso): connect and post review message.
	return nil
}

// PostRobotComments implements the GerritAPI.
func (s gerritServer) PostRobotComments(c context.Context, host, ref string, comments []*track.Comment) error {
	// TODO(emso): connect and post comments
	return nil
}

// MockGerritAPI mocks the GerritAPI interface for testing.
var MockGerritAPI mockGerritAPI

type mockGerritAPI struct {
}

// PostReviewMessage is a mock function for the MockGerritAPI.
//
// For any testing actually using the return value, create a new mock.
func (mockGerritAPI) PostReviewMessage(c context.Context, host, ref, message string) error {
	return nil
}

// PostRobotComments is a mock function for the MockGerritAPI.
//
// For any testing actually using the return value, create a new mock.
func (mockGerritAPI) PostRobotComments(c context.Context, host, ref string, comments []*track.Comment) error {
	return nil
}
