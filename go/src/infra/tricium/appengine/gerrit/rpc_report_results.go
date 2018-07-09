// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"fmt"

	"github.com/golang/protobuf/jsonpb"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/track"
)

const (
	maxComments = 50
)

// ReportResults processes one report results request.
func (r *gerritReporter) ReportResults(c context.Context, req *admin.ReportResultsRequest) (*admin.ReportResultsResponse, error) {
	logging.Fields{
		"run ID": req.RunId,
	}.Infof(c, "[gerrit] ReportResults request received.")
	if req.RunId == 0 {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing run ID")
	}
	if err := reportResults(c, req, GerritServer); err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to report results to Gerrit: %v", err)
	}
	return &admin.ReportResultsResponse{}, nil
}

func reportResults(c context.Context, req *admin.ReportResultsRequest, gerrit API) error {
	// Get Git details first, since other things depend on this.
	request := &track.AnalyzeRequest{ID: req.RunId}
	if err := ds.Get(c, request); err != nil {
		return fmt.Errorf("failed to get AnalyzeRequest entity (ID: %d): %v", req.RunId, err)
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
				return fmt.Errorf("failed to retrieve comments: %v", err)
			}

			// Get the changed lines for this revision.
			changedLines, err := gerrit.GetChangedLines(c, request.GerritHost, request.GerritChange, request.GitRef)

			if err != nil {
				return fmt.Errorf("failed to get changed lines: %v", err)
			}
			// Only include selected comments.
			for _, comment := range fetchedComments {
				var data tricium.Data_Comment
				if comment.Comment != nil {
					if err := jsonpb.UnmarshalString(string(comment.Comment), &data); err != nil {
						logging.WithError(err).Errorf(c, "Failed to unmarshal comment.")
						continue
					}

					// If the file has changed lines tracked, pass over comments that aren't in the diff.
					if lines, ok := changedLines[data.Path]; ok {
						logging.Debugf(c, "Num changed lines for %s is %d.", data.Path, len(lines))
						if data.StartLine != 0 && !isInChangedLines(int(data.StartLine), int(data.EndLine), lines) {
							logging.Debugf(c, "Filtering out comment on lines %d-%d.", data.StartLine, data.EndLine)
							continue
						}
					} else {
						logging.Debugf(c, "File %q is not in changed lines.", data.Path)
						// If the file isn't present in changedLines, it means it was deleted in
						// the patch and therefore has no applicable lines. In this case, filter
						// out all comments that aren't file-level.
						if data.StartLine != 0 {
							continue
						}
					}
				}
				commentKey := ds.KeyForObj(c, comment)
				selection := &track.CommentSelection{ID: 1, Parent: commentKey}
				if err := ds.Get(c, selection); err != nil {
					return fmt.Errorf("failed to get CommentSelection: %v", err)
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

func isInChangedLines(start, end int, changedLines []int) bool {
	for _, line := range changedLines {
		if line >= start && line <= end {
			return true
		}
	}
	return false
}
