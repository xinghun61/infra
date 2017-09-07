// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package step

import (
	"fmt"
	"regexp"
	"sort"
	"strings"

	"golang.org/x/net/context"

	"infra/appengine/sheriff-o-matic/som/client"
	"infra/monitoring/messages"
)

var (
	// FIXME: something more robust.
	compileErrRE = regexp.MustCompile(`(.*)\(([0-9]+),([0-9]+)\) :  error:`)
)

type compileFailure struct {
	FailureLines []string `json:"failure_lines"`
}

func (c *compileFailure) Signature() string {
	return strings.Join(c.FailureLines, ",")
}

func (c *compileFailure) Kind() string {
	return "compile"
}

func (c *compileFailure) Severity() messages.Severity {
	return messages.NoSeverity
}

func (c *compileFailure) Title(bses []*messages.BuildStep) string {
	f := bses[0]
	if len(bses) == 1 {
		return fmt.Sprintf("compile failure on %s/%s", f.Master.Name(), f.Build.BuilderName)
	}

	return fmt.Sprintf("compile failing on %d builders", len(bses))
}

// compileFailureAnalyzer finds compile failures. The current logic for finding
// compile failures isn't all that sophisticated, but it could be improved in
// the future.
func compileFailureAnalyzer(ctx context.Context, fs []*messages.BuildStep) ([]messages.ReasonRaw, []error) {
	results := make([]messages.ReasonRaw, len(fs))

	for i, f := range fs {
		rslt, err := compileAnalyzeFailure(ctx, f)
		if err != nil {
			return nil, []error{err}
		}

		results[i] = rslt
	}

	return results, nil
}

func compileAnalyzeFailure(ctx context.Context, f *messages.BuildStep) (messages.ReasonRaw, error) {
	if f.Step.Name != "compile" {
		return nil, nil
	}

	stdio, err := client.StdioForStep(ctx, f.Master, f.Build.BuilderName, f.Step.Name, f.Build.Number)
	if err != nil {
		return nil, fmt.Errorf("Couldn't get stdio for %s.%s.%s: %v", f.Master.Name(), f.Build.BuilderName, f.Step.Name, err)
	}

	// '(?P<path>.*):(?P<line>\d+):(?P<column>\d+): error:'
	// FIXME: This logic is copied from reasons_splitter.py, which comes with a FIXME.
	// The heuristic here seems pretty weak/brittle.  I've anecdotally seen compile step
	// failures that do not match this filter.
	nextLineIsFailure := false
	failureLines := []string{}
	for _, l := range stdio {
		if !nextLineIsFailure {
			if strings.HasPrefix(l, "FAILED:") {
				nextLineIsFailure = true
			}
			continue
		}
		if compileErrRE.MatchString(l) {
			parts := compileErrRE.FindAllStringSubmatch(l, -1)
			if len(parts) > 0 {
				failureLines = append(failureLines, fmt.Sprintf("%s:%s", parts[0][1], parts[0][2]))
			}
		}
	}
	sorted := failureLines
	sort.Strings(sorted)

	return &compileFailure{
		sorted,
	}, nil
}
