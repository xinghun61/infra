// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"bytes"
	"context"
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
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	gr "golang.org/x/build/gerrit"

	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

const (
	scope = "https://www.googleapis.com/auth/gerritcodereview"
	// Timeout for waiting for a response from Gerrit.
	gerritTimeout = 60 * time.Second
	// MaxChanges is the max number of changes to request from Gerrit.
	//
	// This should be a number small enough so that it can be handled in one
	// request, but also large enough to avoid skipping over changes.
	MaxChanges = 60
	// The timestamp format used by Gerrit (using the reference date).
	// All timestamps are in UTC.
	timeStampLayout = "2006-01-02 15:04:05.000000000"
	// Gerrit's "magic path" to indicate that a comment should be posted to the
	// commit message; see:
	// https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#file-id
	commitMessagePath = "/COMMIT_MSG"
)

// API specifies the Gerrit REST API tuned to the needs of Tricium.
type API interface {
	// QueryChanges sends one query for changes to Gerrit using the provided
	// poll data.
	//
	// The poll data is assumed to correspond to the last seen change before
	// this poll. Even though Gerrit supports paging, we only make one request
	// to Gerrit because polling too many changes can quickly use up too much
	// memory and time.
	//
	// A list of changes is returned in the same order as they were returned by
	// Gerrit. The result tuple includes a boolean value to indicate if the
	// result was truncated.
	QueryChanges(c context.Context, host, project string, lastTimestamp time.Time) ([]gr.ChangeInfo, bool, error)
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
	RobotID        string            `json:"robot_id"`
	RobotRunID     string            `json:"robot_run_id"`
	URL            string            `json:"url,omitempty"`
	Properties     map[string]string `json:"properties"`
	FixSuggestions []*suggestion     `json:"fix_suggestions"`
	ID             string            `json:"id,omitempty"`
	Path           string            `json:"path"`
	Line           int               `json:"line,omitempty"`
	Range          *commentRange     `json:"range,omitempty"`
	Message        string            `json:"message"`
}

type commentRange struct {
	StartLine      int `json:"start_line,omitempty"`
	StartCharacter int `json:"start_character,omitempty"`
	EndLine        int `json:"end_line,omitempty"`
	EndCharacter   int `json:"end_character,omitempty"`
}

type suggestion struct {
	Description  string         `json:"description"`
	Replacements []*replacement `json:"replacements"`
}

type replacement struct {
	Path        string        `json:"path"`
	Replacement string        `json:"replacement"`
	Range       *commentRange `json:"range,omitempty"`
}

func (gerritServer) QueryChanges(c context.Context, host, project string, lastTimestamp time.Time) ([]gr.ChangeInfo, bool, error) {
	var changes []gr.ChangeInfo
	// Compose, connect, and send.
	url := composeChangesQueryURL(host, project, lastTimestamp)
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
	robos := map[string][]*robotCommentInput{} // Map of path to comments for that path.
	for _, storedComment := range storedComments {
		var comment tricium.Data_Comment
		if err := jsonpb.UnmarshalString(string(storedComment.Comment), &comment); err != nil {
			logging.WithError(err).Warningf(c, "Failed to unmarshal comment.")
			break
		}
		path := pathForGerrit(comment.Path)
		if _, ok := robos[path]; !ok {
			robos[path] = []*robotCommentInput{}
		}
		robos[path] = append(robos[path], createRobotComment(c, runID, comment))
	}
	return g.setReview(c, host, change, revision, &reviewInput{
		RobotComments: robos,
		Notify:        "NONE",
		Tag:           "autogenerated:tricium",
	})
}

// GetChangedLines fetches information about which lines were changed.
//
// Added and modified lines are considered changed, and deleted lines are not.
// Note: This method only returns lines based on the patch, and does not know
// about which files are renamed or copied.
func (g gerritServer) GetChangedLines(c context.Context, host, change, revision string) (ChangedLinesInfo, error) {
	return FetchChangedLines(c, host, change, revision)
}

// FetchChangedLines fetches information about which lines were changed which
// includes added and modified lines, and all lines in a moved or copied file.
func FetchChangedLines(c context.Context, host, change, revision string) (ChangedLinesInfo, error) {
	url := fmt.Sprintf(
		"https://%s/a/changes/%s/revisions/%s/patch",
		host, change, PatchSetNumber(revision))
	logging.Debugf(c, "Fetching patch using URL %q", url)
	response, err := fetchResponse(c, url, nil)
	if err != nil {
		return ChangedLinesInfo{}, err
	}
	if string(response) == "" {
		return ChangedLinesInfo{}, errors.New("empty patch response")
	}
	changedLines, err := getChangedLinesFromPatch(string(response))
	if err != nil {
		return ChangedLinesInfo{}, errors.Annotate(err, "unable to extracted changed lines from patch").Err()
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
	c, cancel := context.WithTimeout(c, gerritTimeout)
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
		Message:        comment.Message,
		RobotID:        comment.Category,
		RobotRunID:     strconv.FormatInt(runID, 10),
		URL:            composeRunURL(c, runID),
		Path:           pathForGerrit(comment.Path),
		Properties:     map[string]string{"tricium_comment_uuid": comment.Id},
		FixSuggestions: createFillSuggestions(comment.Suggestions),
	}
	// If no StartLine is given, the comment is assumed to be a file-level comment,
	// and the line field will not be populated so it will be set to zero.
	if comment.StartLine > 0 {
		if comment.EndLine > 0 {
			// If range is set, [the line field] equals the end line of the range.
			// See: https://goo.gl/RdiFDM
			roco.Line = int(comment.EndLine)
			roco.Range = &commentRange{
				StartLine:      int(comment.StartLine),
				EndLine:        int(comment.EndLine),
				StartCharacter: int(comment.StartChar),
				EndCharacter:   int(comment.EndChar),
			}
		} else {
			roco.Line = int(comment.StartLine)
		}
	}
	return roco
}

func createFillSuggestions(suggestions []*tricium.Data_Suggestion) []*suggestion {
	var suggs []*suggestion
	for _, s := range suggestions {
		var replacements []*replacement
		for _, r := range s.Replacements {
			replacements = append(replacements, &replacement{
				Path:        pathForGerrit(r.Path),
				Replacement: r.Replacement,
				Range: &commentRange{
					StartLine:      int(r.StartLine),
					EndLine:        int(r.EndLine),
					StartCharacter: int(r.StartChar),
					EndCharacter:   int(r.EndChar),
				},
			})
		}
		suggs = append(suggs, &suggestion{
			Description:  s.Description,
			Replacements: replacements,
		})
	}
	return suggs
}

// composeRunURL returns the URL for viewing details about a Tricium run.
func composeRunURL(c context.Context, runID int64) string {
	return fmt.Sprintf("https://%s/run/%d", info.DefaultVersionHostname(c), runID)
}

// composeChangesQueryURL composes the URL to query Gerrit for updated changes.
//
// The provided GerritProject object provides Gerrit host, project, and
// timestamp of last poll attempt.
func composeChangesQueryURL(host, project string, lastTimestamp time.Time) string {
	ts := lastTimestamp.Format(timeStampLayout)
	v := url.Values{}
	// We only ask for the latest patch set because we don't want to
	// analyze any previous patch sets. Including the list of files is
	// necessary to create an analyze request.
	v.Add("o", "CURRENT_REVISION")
	v.Add("o", "CURRENT_FILES")
	// Including current commit information allows access to commit message.
	v.Add("o", "CURRENT_COMMIT")
	// Including the account emails is necessary to be able to filter based
	// on the whitelisted_groups field of the project config.
	v.Add("o", "DETAILED_ACCOUNTS")
	v.Add("q", fmt.Sprintf("project:%s after:\"%s\"", project, ts))
	v.Add("n", strconv.Itoa(MaxChanges))
	return fmt.Sprintf("https://%s/a/changes/?%s", host, v.Encode())
}

func (gerritServer) setReview(c context.Context, host, change, revision string, r *reviewInput) error {
	data, err := json.Marshal(r)
	if err != nil {
		return errors.Annotate(err, "failed to marshal ReviewInput").Err()
	}
	url := fmt.Sprintf("https://%s/a/changes/%s/revisions/%s/review", host, change, PatchSetNumber(revision))
	logging.Debugf(c, "Posting comments using URL %q.", url)
	req, err := http.NewRequest("POST", url, bytes.NewReader(data))
	if err != nil {
		return errors.Annotate(err, "failed to create POST request").Err()
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	c, cancel := context.WithTimeout(c, gerritTimeout)
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
		return errors.Annotate(err, "failed to connect to Gerrit, code: %d", resp.StatusCode).Err()
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

// MockRestAPI mocks the GerritAPI interface for testing.
//
// Remembers the last posted message and comments.
type MockRestAPI struct {
	LastMsg      string
	LastComments []*track.Comment
	ChangedLines ChangedLinesInfo
}

// QueryChanges sends one query for changes to Gerrit using the
// provided poll data.
func (*MockRestAPI) QueryChanges(c context.Context, host, project string, ts time.Time) ([]gr.ChangeInfo, bool, error) {
	return []gr.ChangeInfo{}, false, nil
}

// PostRobotComments posts robot comments to a change.
func (m *MockRestAPI) PostRobotComments(c context.Context, host, change, revision string, runID int64, comments []*track.Comment) error {
	m.LastComments = comments
	return nil
}

// GetChangedLines requests the diff info for all files for a
// particular revision and extracts the lines in the "new" post-patch
// version that are considered changed.
func (m *MockRestAPI) GetChangedLines(c context.Context, host, change, revision string) (ChangedLinesInfo, error) {
	return m.ChangedLines, nil
}

// FilterRequestChangedLines will remove changed lines for all files in |request|
// that should be ignored when considering whether to post a comment to the
// file.
func FilterRequestChangedLines(request *track.AnalyzeRequest, changedLines *ChangedLinesInfo) {
	for _, file := range request.Files {
		if file.Status == tricium.Data_RENAMED || file.Status == tricium.Data_COPIED {
			delete(*changedLines, file.Path)
		}
	}
}

// CommentIsInChangedLines checks whether a comment is in the change.
//
// Non-file-level comments that don't overlap with the changed lines
// should be filtered out.
func CommentIsInChangedLines(c context.Context, trackComment *track.Comment, changedLines ChangedLinesInfo) bool {
	var data tricium.Data_Comment
	if trackComment.Comment == nil {
		logging.Errorf(c, "Got a comment with a nil Comment field: %+v", trackComment)
		return false
	}

	if err := jsonpb.UnmarshalString(string(trackComment.Comment), &data); err != nil {
		logging.WithError(err).Errorf(c, "Failed to unmarshal comment.")
		return false
	}

	if len(data.Path) == 0 {
		return true // This is a comment on the commit message, which is always kept.
	}

	if data.StartLine == 0 {
		return true // File-level comment, should be kept.
	}

	// If the file has changed lines tracked, pass over comments that aren't in the diff.
	if lines, ok := changedLines[data.Path]; ok {
		start, end := int(data.StartLine), int(data.EndLine)
		if end > start && data.EndChar == 0 {
			end-- // None of data.EndLine is included in the comment.
		}
		if end == 0 {
			end = start // Line comment.
		}
		if isInChangedLines(start, end, lines) {
			return true
		}
		logging.Debugf(c, "Filtering out comment on lines [%d, %d].", start, end)
		return false
	}
	logging.Debugf(c, "File %q is not in changed lines.", data.Path)
	return false
}

// isInChangedLines checks for overlap between a comment and the change.
//
// Specifically, this returns true if the range defined by [start, end],
// includes any of the lines in changedLines.
func isInChangedLines(start, end int, changedLines []int) bool {
	for _, line := range changedLines {
		if line >= start && line <= end {
			return true
		}
	}
	return false
}

// pathForGerrit returns the path string for a comment for Gerrit.
//
// This may be different if the comment is on the commit message. An empty
// string path from the analyzer signifies that the comment is on the commit
// message. In Gerrit, to indicate this, a "magic path" is used.
func pathForGerrit(inputPath string) string {
	if len(inputPath) == 0 {
		return commitMessagePath
	}
	return inputPath
}
