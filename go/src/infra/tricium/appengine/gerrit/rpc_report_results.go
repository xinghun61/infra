// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"github.com/golang/protobuf/jsonpb"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

const (
	maxComments = 50
)

// ReportResults processes one report results request.
func (r *gerritReporter) ReportResults(c context.Context, req *admin.ReportResultsRequest) (res *admin.ReportResultsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(c, err)
	}()
	logging.Fields{
		"run ID": req.RunId,
	}.Infof(c, "[gerrit] ReportResults request received.")
	if req.RunId == 0 {
		return nil, errors.New("missing run ID", grpcutil.InvalidArgumentTag)
	}
	if err := reportResults(c, req, GerritServer); err != nil {
		return nil, errors.Annotate(err, "failed to report results").
			Tag(grpcutil.InternalTag).Err()
	}
	return &admin.ReportResultsResponse{}, nil
}

func reportResults(c context.Context, req *admin.ReportResultsRequest, gerrit API) error {
	// Get Git details first, since other things depend on this.
	request := &track.AnalyzeRequest{ID: req.RunId}
	if err := ds.Get(c, request); err != nil {
		return errors.Annotate(err, "failed to get AnalyzeRequest").Err()
	}
	var includedComments []*track.Comment
	err := parallel.FanOutIn(func(taskC chan<- func() error) {

		// Get comments.
		taskC <- func() error {
			requestKey := ds.NewKey(c, "AnalyzeRequest", "", req.RunId, nil)
			runKey := ds.NewKey(c, "WorkflowRun", "", 1, requestKey)
			analyzerKey := ds.NewKey(c, "FunctionRun", req.Analyzer, 0, runKey)
			var fetchedComments []*track.Comment
			if err := ds.GetAll(c, ds.NewQuery("Comment").Ancestor(analyzerKey), &fetchedComments); err != nil {
				return errors.Annotate(err, "failed to retrieve comments").Err()
			}

			// Get the changed lines for this revision.
			changedLines, err := gerrit.GetChangedLines(c, request.GerritHost, request.GerritChange, request.GitRef)
			for path, lines := range changedLines {
				logging.Debugf(c, "Num changed lines for %s is %d.", path, len(lines))
			}

			if err != nil {
				return errors.Annotate(err, "failed to get changed lines").Err()
			}

			// Only include selected comments that are within the changed lines.
			for _, comment := range fetchedComments {
				if !commentIsInChangedLines(c, comment, changedLines) {
					continue
				}
				commentKey := ds.KeyForObj(c, comment)
				selection := &track.CommentSelection{ID: 1, Parent: commentKey}
				if err := ds.Get(c, selection); err != nil {
					return errors.Annotate(err, "failed to get CommentSelection").Err()
				}
				if selection.Included {
					includedComments = append(includedComments, comment)
				}
			}
			return nil
		}
	})
	if err != nil {
		return err
	}
	if request.GerritReportingDisabled {
		logging.Fields{
			"project": request.Project,
		}.Infof(c, "Gerrit reporting disabled, not reporting results.")
		return nil
	}
	if len(includedComments) > maxComments {

		logging.Fields{
			"num comments": len(includedComments),
		}.Infof(c, "Too many comments, not reporting results.")
		return nil
	}
	if len(includedComments) == 0 {
		logging.Infof(c, "No comments to report.")
		return nil
	}
	return gerrit.PostRobotComments(c, request.GerritHost, request.GerritChange, request.GitRef, req.RunId, includedComments)
}

// commentIsInChangedLines checks whether a comment is in the change.
//
// Non-file-level comments that don't overlap with the changed lines
// should be filtered out.
func commentIsInChangedLines(c context.Context, trackComment *track.Comment, changedLines ChangedLinesInfo) bool {
	var data tricium.Data_Comment
	if trackComment.Comment == nil {
		logging.Errorf(c, "Got a comment with a nil Comment field: %+v", trackComment)
		return false
	}

	if err := jsonpb.UnmarshalString(string(trackComment.Comment), &data); err != nil {
		logging.WithError(err).Errorf(c, "Failed to unmarshal comment.")
		return false
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
