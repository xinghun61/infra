// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"github.com/golang/protobuf/jsonpb"
	"github.com/waigani/diffparser"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	gr "golang.org/x/build/gerrit"
	"golang.org/x/net/context"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/track"
)

const (
	scope = "https://www.googleapis.com/auth/gerritcodereview"
)

// API specifies the Gerrit REST API tuned to the needs of Tricium.
type API interface {
	// QueryChanges sends one query for changes to Gerrit using the
	// provided poll data and offset.
	//
	// The poll data is assumed to correspond to the last seen change
	// before this poll. Within one poll, the offset is used to handle
	// consecutive calls to this function. A list of changes is returned
	// in the same order as they were returned by Gerrit. The result tuple
	// includes a boolean value to indicate if the result was truncated and
	// more queries should be sent to get the full list of changes. For new
	// queries within the same poll, this function should be called again
	// with an increased offset.
	QueryChanges(c context.Context, host, project string, lastTimestamp time.Time, offset int) ([]gr.ChangeInfo, bool, error)
	// PostRobotComments posts robot comments to a change.
	PostRobotComments(c context.Context, host, change, revision string, runID int64, comments []*track.Comment) error
	// GetChangedLines requests the diff info for all files for a
	// particular revision and extracts the lines in the "new" post-patch
	// version that are considered changed.
	GetChangedLines(c context.Context, host, change, revision string) (ChangedLinesInfo, error)
}

// GerritServer implements RestAPI for the Gerrit service.
var GerritServer gerritServer

// ChangedLinesInfo contains the line numbers that have been touched in
// particular change. The string key is the file name (in posix form), and the
// value is a list of changed (i.e. added or modified) lines (sorted) in the
// destination file.
type ChangedLinesInfo map[string][]int

type gerritServer struct {
}

type reviewInput struct {
	Message       string                          `json:"message,omitempty"`
	Notify        string                          `json:"notify,omitempty"`
	RobotComments map[string][]*robotCommentInput `json:"robot_comments,omitempty"`
	Tag           string                          `json:"tag,omitempty"`
}

type robotCommentInput struct {
	RobotID    string            `json:"robot_id"`
	RobotRunID string            `json:"robot_run_id"`
	URL        string            `json:"url,omitempty"`
	Properties map[string]string `json:"properties"`
	ID         string            `json:"id"`
	Path       string            `json:"path"`
	Line       int               `json:"line,omitempty"`
	Range      *commentRange     `json:"range,omitempty"`
	Message    string            `json:"message"`
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
	body, err := fetchResponse(c, url, map[string]string{
		"Content-Disposition": "application/json",
		"Content-Type":        "application/json",
	})
	// Remove the magic Gerrit JSONP prefix.
	body = bytes.TrimPrefix(body, []byte(")]}'\n"))
	if err != nil {
		return changes, false, err
	}
	if err = json.Unmarshal(body, &changes); err != nil {
		return changes, false, err
	}
	// Check if changes were truncated.
	more := len(changes) > 0 && changes[len(changes)-1].MoreChanges
	return changes, more, nil
}

func (g gerritServer) PostRobotComments(c context.Context, host, change, revision string, runID int64, storedComments []*track.Comment) error {
	robos := map[string][]*robotCommentInput{}
	for _, storedComment := range storedComments {
		var comment tricium.Data_Comment
		if err := jsonpb.UnmarshalString(string(storedComment.Comment), &comment); err != nil {
			logging.Warningf(c, "Failed to unmarshal comment: %v", err)
			break
		}
		if _, ok := robos[comment.Path]; !ok {
			robos[comment.Path] = []*robotCommentInput{}
		}
		robos[comment.Path] = append(robos[comment.Path], createRobotComment(c, runID, comment))
	}
	return g.setReview(c, host, change, revision, &reviewInput{
		RobotComments: robos,
		Notify:        "NONE",
		Tag:           "autogenerated:tricium",
	})
}

func (g gerritServer) GetChangedLines(c context.Context, host, change, revision string) (ChangedLinesInfo, error) {
	url := fmt.Sprintf(
		"https://%s/a/changes/%s/revisions/%s/patch",
		host, change, common.PatchSetNumber(revision))
	logging.Debugf(c, "Fetching patch using URL: %s", url)
	response, err := fetchResponse(c, url, nil)
	if err != nil {
		return ChangedLinesInfo{}, err
	}
	if string(response) == "" {
		return ChangedLinesInfo{}, fmt.Errorf("empty patch response")
	}
	changedLines, err := getChangedLinesFromPatch(string(response))
	if err != nil {
		return ChangedLinesInfo{}, fmt.Errorf("unable to extracted changed lines from patch: %v", err)
	}
	return changedLines, nil
}

func fetchResponse(c context.Context, url string, headers map[string]string) ([]byte, error) {
	// Compose, connect, and send.
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}
	for name, value := range headers {
		req.Header.Set(name, value)
	}
	c, cancel := context.WithTimeout(c, 60*time.Second)
	defer cancel()
	transport, err := auth.GetRPCTransport(c, auth.AsSelf, auth.WithScopes(scope))
	if err != nil {
		return nil, err
	}
	client := &http.Client{Transport: transport}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, err
	}
	// Read and convert response.
	return ioutil.ReadAll(resp.Body)
}

// createRobotComment creates a Gerrit robot comment from a Tricium comment.
//
// Checks for presence of position info to distinguish file comments, line
// comments, and comments with character ranges.
func createRobotComment(c context.Context, runID int64, comment tricium.Data_Comment) *robotCommentInput {
	roco := &robotCommentInput{
		Message:    comment.Message,
		RobotID:    comment.Category,
		RobotRunID: strconv.FormatInt(runID, 10),
		URL:        composeRunURL(c, runID),
		Path:       comment.Path,
		Properties: map[string]string{"tricium_comment_uuid": comment.Id},
	}
	if comment.StartLine > 0 {
		roco.Line = int(comment.StartLine)
		if comment.EndLine > 0 {
			roco.Range = &commentRange{
				StartLine:      int(comment.StartLine),
				EndLine:        int(comment.EndLine),
				StartCharacter: int(comment.StartChar),
				EndCharacter:   int(comment.EndChar),
			}
		}
	}
	return roco
}

// composeRunURL returns the URL for viewing details about a Tricium run.
func composeRunURL(c context.Context, runID int64) string {
	return fmt.Sprintf("https://%s/run/%d", info.DefaultVersionHostname(c), runID)
}

// composeChangesQueryURL composes the URL used to query Gerrit for updated
// changes.
//
// The provided GerritProject object provides Gerrit host, project, and
// timestamp of last poll. The offset is used to handle paging and should be
// incremented during a poll to get all results.
func composeChangesQueryURL(host, project string, lastTimestamp time.Time, offset int) string {
	ts := lastTimestamp.Format(timeStampLayout)
	v := url.Values{}
	v.Add("start", strconv.Itoa(offset))
	// We only ask for the latest patch set because we don't want to
	// analyze any previous patch sets. Including the list of files is
	// necessary to create an analyze request.
	v.Add("o", "CURRENT_REVISION")
	v.Add("o", "CURRENT_FILES")
	// Including the account emails is necessary to be able to filter based
	// on the whitelisted_groups field of the project config.
	v.Add("o", "DETAILED_ACCOUNTS")
	v.Add("q", fmt.Sprintf("project:%s after:\"%s\"", project, ts))
	return fmt.Sprintf("https://%s/a/changes/?%s", host, v.Encode())
}

func (gerritServer) setReview(c context.Context, host, change, revision string, r *reviewInput) error {
	data, err := json.Marshal(r)
	if err != nil {
		return fmt.Errorf("failed to marshal ReviewInput: %v", err)
	}
	logging.Debugf(c, "[gerrit] JSON body: %s", data)
	url := fmt.Sprintf("https://%s/a/changes/%s/revisions/%s/review", host, change, common.PatchSetNumber(revision))
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

func getChangedLinesFromPatch(encodedPatch string) (ChangedLinesInfo, error) {
	rawDiff, err := base64.StdEncoding.DecodeString(encodedPatch)
	if err != nil {
		return ChangedLinesInfo{}, err
	}
	diff, err := diffparser.Parse(string(rawDiff))
	if err != nil {
		return ChangedLinesInfo{}, err
	}
	return diff.Changed(), nil
}

// mockRestAPI mocks the GerritAPI interface for testing.
//
// Remembers the last posted message and comments.
type mockRestAPI struct {
	LastMsg      string
	LastComments []*track.Comment
	ChangedLines ChangedLinesInfo
}

func (*mockRestAPI) QueryChanges(c context.Context, host, project string, ts time.Time, offset int) ([]gr.ChangeInfo, bool, error) {
	return []gr.ChangeInfo{}, false, nil
}

func (m *mockRestAPI) PostRobotComments(c context.Context, host, change, revision string, runID int64, comments []*track.Comment) error {
	m.LastComments = comments
	return nil
}

func (m *mockRestAPI) GetChangedLines(c context.Context, host, change, revision string) (ChangedLinesInfo, error) {
	return m.ChangedLines, nil
}
