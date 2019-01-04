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

func commitLabInventory(ctx context.Context, client gerrit.GerritClient, lab *inventory.Lab) (url string, err error) {
	ls, err := inventory.WriteLabToString(lab)
	if err != nil {
		return "", errors.Annotate(err, "commit lab inventory changes").Err()
	}

	cu, err := commitLabInventoryStr(ctx, client, ls)
	if err != nil {
		return "", errors.Annotate(err, "commit lab inventory changes").Err()
	}
	return cu, nil
}

func commitLabInventoryStr(ctx context.Context, client gerrit.GerritClient, lab string) (url string, err error) {
	inventoryConfig := config.Get(ctx).Inventory
	path := inventoryConfig.LabDataPath
	return commitStringToFile(ctx, client, lab, path)
}

func commitInfraInventory(ctx context.Context, client gerrit.GerritClient, infra *inventory.Infrastructure) (url string, err error) {
	is, err := inventory.WriteInfrastructureToString(infra)
	if err != nil {
		return "", errors.Annotate(err, "commit infra inventory changes").Err()
	}

	cu, err := commitInfraInventoryStr(ctx, client, is)
	if err != nil {
		return "", errors.Annotate(err, "commit infra inventory changes").Err()
	}
	return cu, nil
}

func commitInfraInventoryStr(ctx context.Context, client gerrit.GerritClient, infra string) (url string, err error) {
	inventoryConfig := config.Get(ctx).Inventory
	path := inventoryConfig.InfrastructureDataPath
	return commitStringToFile(ctx, client, infra, path)
}

func commitStringToFile(ctx context.Context, client gerrit.GerritClient, contents string, path string) (url string, err error) {
	inventoryConfig := config.Get(ctx).Inventory

	var changeInfo *gerrit.ChangeInfo
	defer func() {
		if changeInfo != nil {
			abandonChange(ctx, client, changeInfo)
		}
	}()

	changeInfo, err = client.CreateChange(ctx, &gerrit.CreateChangeRequest{
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
		FilePath: path,
		Content:  []byte(contents),
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
