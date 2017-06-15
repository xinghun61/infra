// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"

	"golang.org/x/net/context"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

const (
	gerritScope = "https://www.googleapis.com/auth/gerritcodereview"
)

// GerritAPI specifies the Gerrit service API tuned to the needs of Tricium.
type GerritAPI interface {
	// PostReviewMessage posts a review message to a change.
	PostReviewMessage(c context.Context, host, change, revision, message string) error
	// PostRobotComments posts robot comments to a change.
	PostRobotComments(c context.Context, host, change, revision string, runID int64, comments []*track.Comment) error
}

// GerritServer implements the GerritAPI for the Gerrit service.
var GerritServer gerritServer

type gerritServer struct {
}

type reviewInput struct {
	Message       string                          `json:"message,omitempty"`
	RobotComments map[string][]*robotCommentInput `json:"robot_comments,omitempty"`
}

type robotCommentInput struct {
	RobotID    string        `json:"robot_id"`
	RobotRunID string        `json:"robot_run_id"`
	URL        string        `json:"url,omitempty"`
	ID         string        `json:"id"`
	Path       string        `json:"path"`
	Line       int           `json:"line,omitempty"`
	Range      *commentRange `json:"range,omitempty"`
	Message    string        `json:"message"`
}

type commentRange struct {
	StartLine      int `json:"start_line,omitempty"`
	StartCharacter int `json:"start_character,omitempty"`
	EndLine        int `json:"end_line,omitempty"`
	EndCharacter   int `json:"end_character,omitempty"`
}

// PostReviewMessage implements the GerritAPI.
func (g gerritServer) PostReviewMessage(c context.Context, host, change, revision, message string) error {
	return g.setReview(c, host, change, revision, &reviewInput{Message: message})
}

// PostRobotComments implements the GerritAPI.
func (g gerritServer) PostRobotComments(ctx context.Context, host, change, revision string, runID int64, comments []*track.Comment) error {
	robos := map[string][]*robotCommentInput{}
	for _, c := range comments {
		var comment tricium.Data_Comment
		if err := json.Unmarshal([]byte(c.Comment), &comment); err != nil {
			logging.Warningf(ctx, "failed to unmarshal comment: %v", err)
			break
		}
		if _, ok := robos[comment.Path]; !ok {
			robos[comment.Path] = []*robotCommentInput{}
		}
		robos[comment.Path] = append(robos[comment.Path], &robotCommentInput{
			Message:    comment.Message,
			RobotID:    comment.Category,
			RobotRunID: strconv.FormatInt(runID, 10),
			URL:        comment.Url,
			Path:       comment.Path,
			Line:       int(comment.StartLine),
			Range: &commentRange{
				StartLine:      int(comment.StartLine),
				EndLine:        int(comment.EndLine),
				StartCharacter: int(comment.StartChar),
				EndCharacter:   int(comment.EndChar),
			},
		})
	}
	return g.setReview(ctx, host, change, revision, &reviewInput{RobotComments: robos})
}

func (gerritServer) setReview(c context.Context, host, change, revision string, r *reviewInput) error {
	data, err := json.Marshal(r)
	if err != nil {
		return fmt.Errorf("failed to marshal ReviewInput: %v", err)
	}
	url := fmt.Sprintf("%s/changes/%s/revision/%s/review", host, change, revision)
	logging.Infof(c, "Using Gerrit Set Review URL: %s", url)
	req, err := http.NewRequest("POST", url, bytes.NewReader(data))
	if err != nil {
		return fmt.Errorf("failed to create POST request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	t, err := auth.GetRPCTransport(c, auth.AsSelf, auth.WithScopes(gerritScope))
	if err != nil {
		return fmt.Errorf("failed to create oauth client: %v", err)

	}
	client := &http.Client{Transport: t}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed to connect to Gerrit: %v", err)
	}
	return nil
}

// MockGerritAPI mocks the GerritAPI interface for testing.
var MockGerritAPI mockGerritAPI

type mockGerritAPI struct {
}

// PostReviewMessage is a mock function for the MockGerritAPI.
//
// For any testing actually using the return value, create a new mock.
func (mockGerritAPI) PostReviewMessage(c context.Context, host, change, revision, message string) error {
	return nil
}

// PostRobotComments is a mock function for the MockGerritAPI.
//
// For any testing actually using the return value, create a new mock.
func (mockGerritAPI) PostRobotComments(c context.Context, host, change, revision string, runID int64, comments []*track.Comment) error {
	return nil
}
