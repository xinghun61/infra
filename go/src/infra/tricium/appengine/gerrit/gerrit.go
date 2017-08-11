// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"

	gr "golang.org/x/build/gerrit"
	"golang.org/x/net/context"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

const (
	scope = "https://www.googleapis.com/auth/gerritcodereview"
)

// API specifies the Gerrit REST API tuned to the needs of Tricium.
type API interface {
	// QueryChanges sends one query for changes to Gerrit using the provided poll data and offset.
	//
	// The poll data is assumed to correspond to the last seen change before this poll. Within one
	// poll, the offset is used to handle consecutive calls to this function.
	// A list of changes is returned in the same order as they were returned by Gerrit.
	// The result tuple includes a boolean value to indicate of the result was truncated and
	// more queries should be sent to get the full list of changes. For new queries within the same
	// poll, this function should be called again with an increased offset.
	QueryChanges(c context.Context, host, project string, lastTimestamp time.Time, offset int) ([]gr.ChangeInfo, bool, error)
	// PostReviewMessage posts a review message to a change.
	PostReviewMessage(c context.Context, host, change, revision, message string) error
	// PostRobotComments posts robot comments to a change.
	PostRobotComments(c context.Context, host, change, revision string, runID int64, comments []*track.Comment) error
}

// GerritServer implements RestAPI for the Gerrit service.
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

func (gerritServer) QueryChanges(c context.Context, host, project string, lastTimestamp time.Time, offset int) ([]gr.ChangeInfo, bool, error) {
	var changes []gr.ChangeInfo
	// Compose, connect, and send.
	url := composeChangesQueryURL(host, project, lastTimestamp, offset)
	logging.Debugf(c, "Using URL: %s", url)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return changes, false, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	c, cancel := context.WithTimeout(c, 60*time.Second)
	defer cancel()
	transport, err := auth.GetRPCTransport(c, auth.AsSelf, auth.WithScopes(scope))
	if err != nil {
		return changes, false, err
	}
	client := &http.Client{Transport: transport}
	resp, err := client.Do(req)
	if err != nil {
		return changes, false, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return changes, false, err
	}
	// Read and convert response.
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return changes, false, err
	}
	// Remove the magic Gerrit prefix.
	body = bytes.TrimPrefix(body, []byte(")]}'\n"))
	if err = json.Unmarshal(body, &changes); err != nil {
		return changes, false, err
	}
	// Check if changes were truncated.
	more := len(changes) > 0 && changes[len(changes)-1].MoreChanges
	return changes, more, nil
}

func (g gerritServer) PostReviewMessage(c context.Context, host, change, revision, message string) error {
	return g.setReview(c, host, change, revision, &reviewInput{Message: message})
}

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
		// TODO(emso): Values used for testing, update to use values in comment after making sure they are added.
		path := "README.md"
		robos[path] = append(robos[comment.Path], &robotCommentInput{
			Message:    comment.Message,
			RobotID:    comment.Category,
			RobotRunID: strconv.FormatInt(runID, 10),
			Path:       path,
		})
		/*
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
		   i		})
		*/
	}
	return g.setReview(ctx, host, change, revision, &reviewInput{RobotComments: robos})
}

// composeChangesQueryURL composes the URL used to query Gerrit for updated changes.
//
// The provided GerritProject object provides Gerrit instance, project, and timestamp
// of last poll.
// The offset is used to handle paging and should be incremented during a poll to get
// all results.
func composeChangesQueryURL(host, project string, lastTimestamp time.Time, offset int) string {
	ts := lastTimestamp.Format(timeStampLayout)
	v := url.Values{}
	v.Add("start", strconv.Itoa(offset))
	v.Add("o", "CURRENT_REVISION")
	v.Add("o", "CURRENT_FILES")
	v.Add("q", fmt.Sprintf("project:%s after:\"%s\"", project, ts))
	return fmt.Sprintf("%s/a/changes/?%s", host, v.Encode())
}

func (gerritServer) setReview(c context.Context, host, change, revision string, r *reviewInput) error {
	data, err := json.Marshal(r)
	if err != nil {
		return fmt.Errorf("failed to marshal ReviewInput: %v", err)
	}
	logging.Debugf(c, "[gerrit] JSON body: %s", data)
	url := fmt.Sprintf("%s/a/changes/%s/revisions/%s/review", host, change, revision)
	logging.Infof(c, "Using Gerrit Set Review URL: %s", url)
	req, err := http.NewRequest("POST", url, bytes.NewReader(data))
	if err != nil {
		return fmt.Errorf("failed to create POST request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	// TODO(emso): Extract timeout to a common config for all Gerrit connections.
	c, cancel := context.WithTimeout(c, 60*time.Second)
	defer cancel()
	transport, err := auth.GetRPCTransport(c, auth.AsSelf, auth.WithScopes(scope))
	if err != nil {
		return err
	}
	client := &http.Client{Transport: transport}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed to connect to Gerrit, code: %d, %v", resp.StatusCode, err)
	}
	return nil
}

// mockRestAPI mocks the GerritAPI interface for testing.
//
// Remembers the last posted message and comments.
type mockRestAPI struct {
	LastMsg      string
	LastComments []*track.Comment
}

func (*mockRestAPI) QueryChanges(c context.Context, host, project string, ts time.Time, offset int) ([]gr.ChangeInfo, bool, error) {
	return []gr.ChangeInfo{}, false, nil
}

func (m *mockRestAPI) PostReviewMessage(c context.Context, host, change, revision, msg string) error {
	m.LastMsg = msg
	return nil
}

func (m *mockRestAPI) PostRobotComments(c context.Context, host, change, revision string, runID int64, comments []*track.Comment) error {
	m.LastComments = comments
	return nil
}
