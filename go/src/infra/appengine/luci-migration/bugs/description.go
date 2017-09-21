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

package bugs

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

var descriptionTmpl = template.Must(template.New("").
	Funcs(template.FuncMap{
		"pathEscape": common.PathEscape,
	}).
	Parse(strings.TrimSpace(`
Migrate builder {{.Builder.ID}} to LUCI.

Buildbot: https://ci.chromium.org/buildbot/{{.Builder.ID.Master|pathEscape}}/{{.Builder.ID.Builder|pathEscape}}
LUCI: https://ci.chromium.org/buildbucket/{{.Builder.LUCIBuildbucketBucket|pathEscape}}/{{.Builder.ID.Builder|pathEscape}}

Migration app will be posting updates on changes of the migration status.
For the latest status, see
https://{{.Hostname}}/masters/{{.Builder.ID.Master|pathEscape}}/builders/{{.Builder.ID.Builder|pathEscape}}

Migration app will close this bug when the builder is entirely migrated from Buildbot to LUCI.
`)))

// DescriptionVersion is the current version of bug description.
const DescriptionVersion = 1

func bugDescription(c context.Context, builder *storage.Builder) string {
	descArgs := map[string]interface{}{
		"Builder":  builder,
		"Hostname": info.DefaultVersionHostname(c),
	}
	buf := &bytes.Buffer{}
	if err := descriptionTmpl.Execute(buf, descArgs); err != nil {
		panic(fmt.Errorf("bug desription didn't render: %s", err))
	}
	return buf.String()
}

// CreateBuilderBug creates a Monorail issue to migrate the builder to LUCI.
// builder.IssueID must specify the target monorail hostname and project.
// On success, builder.IssueID.ID is set to the created issue ID and
// IssueDescriptionVersion is updated.
func CreateBuilderBug(c context.Context, client ClientFactory, builder *storage.Builder) error {
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
		ProjectId: builder.IssueID.Project,
		SendEmail: true,
		Issue: &monorail.Issue{
			Status:      "Available",
			Summary:     fmt.Sprintf("Migrate %q to LUCI", builder.ID.Builder),
			Description: bugDescription(c, builder),
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

	res, err := client(builder.IssueID.Hostname).InsertIssue(c, req)
	if err != nil {
		return errors.Annotate(err, "InsertIssue RPC failed").Err()
	}

	builder.IssueID.ID = int(res.Issue.Id)
	builder.IssueDescriptionVersion = DescriptionVersion
	return nil
}

// UpdateBuilderBugDescription updates description of builder's monorail bug.
// On success, updates builder.IssueDescriptionVersion.
func UpdateBuilderBugDescription(c context.Context, client ClientFactory, builder *storage.Builder) error {
	req := &monorail.InsertCommentRequest{
		Issue: &monorail.IssueRef{
			ProjectId: builder.IssueID.Project,
			IssueId:   int32(builder.IssueID.ID),
		},
		Comment: &monorail.InsertCommentRequest_Comment{
			Content: bugDescription(c, builder),
			Updates: &monorail.Update{IsDescription: true},
		},
	}

	_, err := client(builder.IssueID.Hostname).InsertComment(c, req)
	if err != nil {
		return errors.Annotate(err, "InsertComment RPC failed").Err()
	}
	builder.IssueDescriptionVersion = DescriptionVersion
	return nil
}
