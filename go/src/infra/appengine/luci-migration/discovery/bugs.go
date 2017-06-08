// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package discovery

import (
	"bytes"
	"fmt"
	"infra/monorail"
	"net/url"
	"strings"
	"text/template"
	"unicode"

	"golang.org/x/net/context"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"

	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/common/errors"
)

const monorailProject = "chromium"

var builderBugDescriptionTmpl = template.Must(template.New("").
	Funcs(template.FuncMap{
		"pathEscape": func(s string) string {
			// cannot use url.PathEscape because AppEngine is on Go 1.6
			u := url.URL{Path: s}
			return u.EscapedPath()
		},
	}).
	Parse(strings.TrimSpace(`
Migrate builder {{.Builder.ID}} to LUCI.

Buildbot: https://ci.chromium.org/buildbot/{{.Builder.ID.Master|pathEscape}}/{{.Builder.ID.Builder|pathEscape}}
LUCI: https://ci.chromium.org/buildbucket/{{.Builder.LUCIBuildbucketBucket|pathEscape}}/{{.Builder.LUCIBuildbucketBuilder|pathEscape}}

I will be posting updates on changes of the migration status.
For the latest status, see
https://{{.Hostname}}/masters/{{.Builder.ID.Master|pathEscape}}/builders/{{.Builder.ID.Builder|pathEscape}}
`)))

// createBuilderBug creates a Monorail issue to migrate the builder to LUCI.
func createBuilderBug(c context.Context, client monorail.MonorailClient, builder *storage.Builder) (issueID int, err error) {
	descArgs := map[string]interface{}{
		"Builder":  builder,
		"Hostname": info.DefaultVersionHostname(c),
	}
	descBuf := &bytes.Buffer{}
	if err := builderBugDescriptionTmpl.Execute(descBuf, descArgs); err != nil {
		return 0, errors.Annotate(err).Reason("could not execute description template").Err()
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
			Status:      "Untriaged",
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
		return 0, errors.Annotate(err).Reason("InsertIssue RPC failed").Err()
	}

	return int(res.Issue.Id), nil
}
