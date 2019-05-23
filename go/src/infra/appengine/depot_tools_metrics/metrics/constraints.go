// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package metrics

import (
	"fmt"

	"go.chromium.org/luci/common/data/stringset"
	"infra/appengine/depot_tools_metrics/schema"
)

func checkConstraints(m schema.Metrics) error {
	for _, httpRequest := range m.HttpRequests {
		if err := checkHTTPRequestConstraints(*httpRequest); err != nil {
			return err
		}
	}
	for _, subCommand := range m.SubCommands {
		if err := checkSubCommandConstraints(*subCommand); err != nil {
			return err
		}
	}
	unknownArguments := unknownStrings(knownArguments, m.Arguments)
	unknownProjectURLs := unknownStrings(knownProjectURLs, m.ProjectUrls)
	switch {
	case m.MetricsVersion < 0:
		return fmt.Errorf("invalid metrics version: %v", m.MetricsVersion)
	case m.Timestamp < 0:
		return fmt.Errorf("invalid timestamp: %v", m.Timestamp)
	case m.Command != "" && !knownCommands.Has(m.Command):
		return fmt.Errorf("unknown command: %v", m.Command)
	case unknownArguments.Len() != 0:
		return fmt.Errorf("unknown arguments: %v", unknownArguments)
	case m.ExecutionTime < 0:
		return fmt.Errorf("invalid execution time: %v", m.ExecutionTime)
	case unknownProjectURLs.Len() != 0:
		return fmt.Errorf("unknown project URLs: %v", unknownProjectURLs)
	case m.DepotToolsAge < 0:
		return fmt.Errorf("invalid depot_tools age: %v", m.DepotToolsAge)
	case m.HostArch != "" && !knownArchs.Has(m.HostArch):
		return fmt.Errorf("unknown architecture: %v", m.HostArch)
	case m.HostOs != "" && !knownOSs.Has(m.HostOs):
		return fmt.Errorf("unknown OS: %v", m.HostOs)
	case m.PythonVersion != "" && !pythonVersionRegex.MatchString(m.PythonVersion):
		return fmt.Errorf("invalid python version: %v", m.PythonVersion)
	case m.GitVersion != "" && !gitVersionRegex.MatchString(m.GitVersion):
		return fmt.Errorf("invalid git version: %v", m.GitVersion)
	default:
		return nil
	}
}

func checkSubCommandConstraints(c schema.SubCommand) error {
	unknownArguments := unknownStrings(knownSubCommandArguments, c.Arguments)
	switch {
	case c.Command != "" && !knownSubCommands.Has(c.Command):
		return fmt.Errorf("invalid sub-command: %v", c.Command)
	case unknownArguments.Len() != 0:
		return fmt.Errorf("unknown sub-command arguments: %v", unknownArguments)
	case c.ExecutionTime < 0:
		return fmt.Errorf("invalid sub-command execution time: %v", c.ExecutionTime)
	default:
		return nil
	}
}

func checkHTTPRequestConstraints(r schema.HttpRequest) error {
	unknownArguments := unknownStrings(knownHTTPArguments, r.Arguments)
	switch {
	case r.Host != "" && !knownHTTPHosts.Has(r.Host):
		return fmt.Errorf("unknown HTTP host: %v", r.Host)
	case r.Method != "" && !knownHTTPMethods.Has(r.Method):
		return fmt.Errorf("unknown HTTP method: %v", r.Method)
	case r.Path != "" && !knownHTTPPaths.Has(r.Path):
		return fmt.Errorf("unknown HTTP path: %v", r.Path)
	case unknownArguments.Len() != 0:
		return fmt.Errorf("unknown HTTP arguments: %v", unknownArguments)
	case r.Status < 200 || 599 < r.Status:
		return fmt.Errorf("invalid HTTP status: %v", r.Status)
	case r.ResponseTime < 0:
		return fmt.Errorf("invalid response time: %v", r.ResponseTime)
	default:
		return nil
	}
}

func unknownStrings(knownStrings stringset.Set, strings []string) stringset.Set {
	return stringset.NewFromSlice(strings...).Difference(knownStrings)
}
