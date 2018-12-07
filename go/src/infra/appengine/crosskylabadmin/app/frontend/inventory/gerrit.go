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

package inventory

import (
	"fmt"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/libs/skylab/inventory"
	"net/url"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
)

func commitInventory(ctx context.Context, client gerrit.GerritClient, lab *inventory.Lab) (string, error) {
	ls, err := inventory.WriteLabToString(lab)
	if err != nil {
		return "", errors.Annotate(err, "commit inventory changes").Err()
	}

	cu, err := commitInventoryStr(ctx, client, ls)
	if err != nil {
		return "", errors.Annotate(err, "commit inventory changes").Err()
	}
	return cu, nil
}

func commitInventoryStr(ctx context.Context, client gerrit.GerritClient, lab string) (string, error) {
	var changeInfo *gerrit.ChangeInfo
	defer func() {
		if changeInfo != nil {
			abandonChange(ctx, client, changeInfo)
		}
	}()

	inventoryConfig := config.Get(ctx).Inventory

	changeInfo, err := client.CreateChange(ctx, &gerrit.CreateChangeRequest{
		Project: inventoryConfig.Project,
		Ref:     inventoryConfig.Branch,
		Subject: changeSubject(ctx),
	})
	if err != nil {
		return "", err
	}

	if _, err = client.ChangeEditFileContent(ctx, &gerrit.ChangeEditFileContentRequest{
		Number:   changeInfo.Number,
		Project:  changeInfo.Project,
		FilePath: inventoryConfig.DataPath,
		Content:  []byte(lab),
	}); err != nil {
		return "", err
	}
	if _, err = client.ChangeEditPublish(ctx, &gerrit.ChangeEditPublishRequest{
		Number:  changeInfo.Number,
		Project: changeInfo.Project,
	}); err != nil {
		return "", err
	}

	ci, err := client.GetChange(ctx, &gerrit.GetChangeRequest{
		Number:  changeInfo.Number,
		Options: []gerrit.QueryOption{gerrit.QueryOption_CURRENT_REVISION},
	})
	if err != nil {
		return "", err
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
		return "", err
	}

	if _, err := client.SubmitChange(ctx, &gerrit.SubmitChangeRequest{
		Number:  changeInfo.Number,
		Project: changeInfo.Project,
	}); err != nil {
		return "", err
	}

	cu, err := changeURL(inventoryConfig.GerritHost, changeInfo)
	if err != nil {
		return "", err
	}

	// Successful: do not abandon change beyond this point.
	changeInfo = nil
	return cu, nil
}

func changeURL(host string, ci *gerrit.ChangeInfo) (string, error) {
	p, err := url.PathUnescape(ci.Project)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("https://%s/c/%s/+/%d", host, p, ci.Number), nil
}

func changeSubject(ctx context.Context) string {
	user := "anonymous"
	as := auth.GetState(ctx)
	if as != nil {
		user = string(as.User().Identity)
	}
	return fmt.Sprintf("balance pool by %s for %s", info.AppID(ctx), user)
}

func abandonChange(ctx context.Context, client gerrit.GerritClient, ci *gerrit.ChangeInfo) {
	if _, err := client.AbandonChange(ctx, &gerrit.AbandonChangeRequest{
		Number:  ci.Number,
		Project: ci.Project,
		Message: "balance-pool: cleanup on error",
	}); err != nil {
		logging.Errorf(ctx, "Failed to abandon change %v on error", ci)
	}
}
