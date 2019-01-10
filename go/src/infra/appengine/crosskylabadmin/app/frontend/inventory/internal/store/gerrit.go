// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package store

import (
	"fmt"
	"net/url"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/common/retry/transient"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
)

// commitFileContents commits given files via gerrit.
//
// project is the git project to commit to.
// branch is the git branch to commit to.
// baseCommitSha is the SHA1 of the base commit over which a change should be created.
// reason is the short human readable reason for this change, to be used in commit message description; e.g. "balance pool"
// fileContents maps file paths in the repo to the new contents at those paths.
//
// commitFileContents returns the gerrit change number for the commit.
func commitFileContents(ctx context.Context, client gerrit.GerritClient, project string, branch string, baseCommitSha string, reason string, fileContents map[string]string) (int, error) {
	var changeInfo *gerrit.ChangeInfo
	defer func() {
		if changeInfo != nil {
			abandonChange(ctx, client, changeInfo)
		}
	}()

	changeInfo, err := client.CreateChange(ctx, &gerrit.CreateChangeRequest{
		Project:    project,
		Ref:        branch,
		Subject:    changeSubject(ctx, reason),
		BaseCommit: baseCommitSha,
	})
	if err != nil {
		return -1, err
	}

	for path, contents := range fileContents {
		if _, err = client.ChangeEditFileContent(ctx, &gerrit.ChangeEditFileContentRequest{
			Number:   changeInfo.Number,
			Project:  changeInfo.Project,
			FilePath: path,
			Content:  []byte(contents),
		}); err != nil {
			return -1, err
		}
	}
	if _, err = client.ChangeEditPublish(ctx, &gerrit.ChangeEditPublishRequest{
		Number:  changeInfo.Number,
		Project: changeInfo.Project,
	}); err != nil {
		return -1, err
	}

	ci, err := client.GetChange(ctx, &gerrit.GetChangeRequest{
		Number:  changeInfo.Number,
		Options: []gerrit.QueryOption{gerrit.QueryOption_CURRENT_REVISION},
	})
	if err != nil {
		return -1, err
	}

	if _, err = client.SetReview(ctx, &gerrit.SetReviewRequest{
		Number:     changeInfo.Number,
		Project:    changeInfo.Project,
		RevisionId: ci.CurrentRevision,
		Labels: map[string]int32{
			"Code-Review": 2,
			"Verified":    1,
		},
	}); err != nil {
		return -1, err
	}

	if _, err := client.SubmitChange(ctx, &gerrit.SubmitChangeRequest{
		Number:  changeInfo.Number,
		Project: changeInfo.Project,
	}); err != nil {
		// Mark this error as transient so that the operation will be retried.
		// Errors in submit are mostly caused because of conflict with a concurrent
		// change to the inventory.
		return -1, errors.Annotate(err, "commit file conents").Tag(transient.Tag).Err()
	}

	cn := int(changeInfo.Number)
	// Successful: do not abandon change beyond this point.
	changeInfo = nil
	return cn, nil
}

// changeURL returns a URL to the gerrit change give the gerrit host, project and changeNumber.
func changeURL(host string, project string, changeNumber int) (string, error) {
	p, err := url.PathUnescape(project)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("https://%s/c/%s/+/%d", host, p, changeNumber), nil
}

func changeSubject(ctx context.Context, reason string) string {
	user := "anonymous"
	as := auth.GetState(ctx)
	if as != nil {
		user = string(as.User().Identity)
	}
	return fmt.Sprintf("%s by %s for %s", reason, info.AppID(ctx), user)
}

func abandonChange(ctx context.Context, client gerrit.GerritClient, ci *gerrit.ChangeInfo) {
	if _, err := client.AbandonChange(ctx, &gerrit.AbandonChangeRequest{
		Number:  ci.Number,
		Project: ci.Project,
		Message: "CL cleanup on error",
	}); err != nil {
		logging.Errorf(ctx, "Failed to abandon change %v on error", ci)
	}
}
