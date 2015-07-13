// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyzer

import (
	"fmt"
	"regexp"
	"strings"

	"infra/monitoring/client"
)

var (
	// TODO: something more robust.
	compileErrRE = regexp.MustCompile(`(.*)\(([0-9]+),([0-9]+)\) :  error:`)
)

// CompileFailureAnalyzer determines the reasons, if any, for a compilation step failure.
type CompileFailureAnalyzer struct {
	Reader client.Reader
}

// Analyze returns the reasons, if any, for the step if it was a compilation failure. Also returns
// whether or not the analyzer applied to the failure and any error in encountered while
// running.
func (a *CompileFailureAnalyzer) Analyze(f stepFailure) (*StepAnalyzerResult, error) {
	ret := &StepAnalyzerResult{}
	if f.step.Name != "compile" {
		return ret, nil
	}
	ret.Recognized = true

	stdio, err := a.Reader.StdioForStep(f.masterName, f.builderName, f.step.Name, f.build.Number)
	if err != nil {
		return nil, fmt.Errorf("Couldn't get stdio for %s.%s.%s: %v", f.masterName, f.builderName, f.step.Name, err)
	}

	// '(?P<path>.*):(?P<line>\d+):(?P<column>\d+): error:'
	// FIXME: This logic is copied from reasons_splitter.py, which comes with a FIXME.
	// The heuristic here seems pretty weak/brittle.  I've anecdotally seen compile step
	// failures that do not match this filter.
	nextLineIsFailure := false
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
				ret.Reasons = append(ret.Reasons, fmt.Sprintf("%s:%s", parts[0][1], parts[0][2]))
			}
			log.Errorf("Error parsing stdio for compiler error: %v", parts)
		}
	}

	return ret, nil
}
