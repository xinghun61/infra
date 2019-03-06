// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"fmt"
	"infra/tricium/appengine/common/track"
	"regexp"
)

var refRegexp = regexp.MustCompile("^refs/changes/[0-9]+/([0-9]+)/([0-9]+)$")

// PatchSetNumber extracts the patch set number from a revision ref.
func PatchSetNumber(revision string) string {
	_, patch := ExtractCLPatchSetNumbers(revision)
	return patch
}

// CLNumber extracts the CL number from a revision ref.
func CLNumber(revision string) string {
	cl, _ := ExtractCLPatchSetNumbers(revision)
	return cl
}

// CreateURL makes a URL to link to a particular revision.
func CreateURL(host, revision string) string {
	cl, patch := ExtractCLPatchSetNumbers(revision)
	if cl == "" && patch == "" {
		return ""
	}
	return fmt.Sprintf("%s/c/%s/%s", host, cl, patch)
}

// ExtractCLPatchSetNumbers extracts CL/patch numbers from a revision ref.
func ExtractCLPatchSetNumbers(revision string) (string, string) {
	matches := refRegexp.FindStringSubmatch(revision)
	if matches == nil {
		return "", ""
	}
	return matches[1], matches[2]
}

// IsGerritProjectRequest determines if the |request| is for a Gerrit project.
func IsGerritProjectRequest(request *track.AnalyzeRequest) bool {
	return request.GerritProject != "" && request.GerritChange != ""
}
