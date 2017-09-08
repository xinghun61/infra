// Copyright 2017 The LUCI Authors.
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

package discovery

import (
	"bytes"
	"fmt"
	"infra/monorail"
	"strings"
	"text/template"
	"unicode"

	"golang.org/x/net/context"

	"infra/appengine/luci-migration/common"
	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/errors"
)

const monorailProject = "chromium"

var builderBugDescriptionTmpl = template.Must(template.New("").
	Funcs(template.FuncMap{
		"pathEscape": common.PathEscape,
	}).
	Parse(strings.TrimSpace(`
Migrate builder {{.Builder.ID}} to LUCI.

Buildbot: https://ci.chromium.org/buildbot/{{.Builder.ID.Master|pathEscape}}/{{.Builder.ID.Builder|pathEscape}}
LUCI: https://ci.chromium.org/buildbucket/{{.Builder.LUCIBuildbucketBucket|pathEscape}}/{{.Builder.LUCIBuildbucketBuilder|pathEscape}}

Migration app will be posting updates on changes of the migration status.
For the latest status, see
https://{{.Hostname}}/masters/{{.Builder.ID.Master|pathEscape}}/builders/{{.Builder.ID.Builder|pathEscape}}

Migration app will close this bug when the builder is entirely migrated from Buildbot to LUCI.
`)))

// createBuilderBug creates a Monorail issue to migrate the builder to LUCI.
func createBuilderBug(c context.Context, client monorail.MonorailClient, builder *storage.Builder) (issueID int, err error) {
	descArgs := map[string]interface{}{
		"Builder":  builder,
		"Hostname": info.DefaultVersionHostname(c),
	}
	descBuf := &bytes.Buffer{}
	if err := builderBugDescriptionTmpl.Execute(descBuf, descArgs); err != nil {
		return 0, errors.Annotate(err, "could not execute description template").Err()
	}

	// excludes invalid chars from a label, like Monorail server does.
	excludeInvalid := func(s string) string {
		return strings.Map(func(r rune) rune {
			if unicode.IsDigit(r) || unicode.IsLetter(r) || r == '.' || r == '_' {
				return r
			}
			return -1
		}, s)
	}

	req := &monorail.InsertIssueRequest{
		ProjectId: monorailProject,
		SendEmail: true,
		Issue: &monorail.Issue{
			Status:      "Available",
			Summary:     fmt.Sprintf("Migrate %q to LUCI", builder.ID.Builder),
			Description: descBuf.String(),
			Components:  []string{"Infra>Platform"},
			Labels: []string{
				"Via-Luci-Migration",
				"Type-Task",
				"Pri-3",
				"Master-" + excludeInvalid(builder.ID.Master),
				"Restrict-View-Google",
			},
		},
	}
	if builder.OS != config.OS_UNSET_OS {
		// Monorail tolerates all-caps OS names.
		req.Issue.Labels = append(req.Issue.Labels, "OS-"+builder.OS.String())
	}

	res, err := client.InsertIssue(c, req)
	if err != nil {
		return 0, errors.Annotate(err, "InsertIssue RPC failed").Err()
	}

	return int(res.Issue.Id), nil
}
