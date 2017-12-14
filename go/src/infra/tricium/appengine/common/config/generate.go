// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"path/filepath"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
)

// Generate generates a Tricium workflow based on the provided configs and paths to analyze.
//
// The workflow will be computed from the validated and merged config for the project in question,
// and filtered to only include workers relevant to the files to be analyzed.
func Generate(sc *tricium.ServiceConfig, pc *tricium.ProjectConfig, paths []string) (*admin.Workflow, error) {
	vpc, err := Validate(sc, pc)
	if err != nil {
		return nil, fmt.Errorf("failed to validate project config: %v", err)
	}
	pd := tricium.LookupProjectDetails(sc, pc.Name)
	if pd == nil {
		return nil, fmt.Errorf("unknown project, project: %s", pc.Name)
	}
	var workers []*admin.Worker
	functions := map[string]*tricium.Function{}
	for _, s := range vpc.Selections {
		if _, ok := functions[s.Function]; !ok {
			f := tricium.LookupProjectFunction(vpc, s.Function)
			if f == nil {
				return nil, fmt.Errorf("failed to lookup project function: %v", err)
			}
			functions[s.Function] = f
		}
		ok, err := includeFunction(functions[s.Function], paths)
		if err != nil {
			return nil, fmt.Errorf("failed include function check: %v", err)
		} else if ok {
			w, err := createWorker(s, sc, functions[s.Function])
			if err != nil {
				return nil, fmt.Errorf("failed to create worker: %v", err)
			}
			workers = append(workers, w)
		}
	}
	if err := resolveSuccessorWorkers(sc, workers); err != nil {
		return nil, fmt.Errorf("workflow is not sane: %v", err)
	}
	return &admin.Workflow{
		ServiceAccount: pd.SwarmingServiceAccount,
		Workers:        workers,
		SwarmingServer: sc.SwarmingServer,
		IsolateServer:  sc.IsolateServer,
	}, nil
}

// resolveSuccessorWorkers computes successor workers based on data dependencies.
//
// The resulting list of successors are added to the Next fields of the provided workers.
// Platform-specific data types add an additional platform check to make successors of
// workers providing a platform-specific type only include successors running on that
// platform.
//
// The resulting workflow is sanity checked and returns an error on failure.
func resolveSuccessorWorkers(sc *tricium.ServiceConfig, workers []*admin.Worker) error {
	specific := map[tricium.Data_Type]bool{}
	for _, d := range sc.GetDataDetails() {
		if _, ok := specific[d.Type]; ok {
			return fmt.Errorf("multiple declarations of the same data type in the service config, type: %s", d)
		}
		specific[d.Type] = d.IsPlatformSpecific
	}
	needs := map[tricium.Data_Type][]*admin.Worker{}
	for _, w := range workers {
		needs[w.Needs] = append(needs[w.Needs], w)
	}
	for _, w := range workers {
		for _, ws := range needs[w.Provides] {
			if !specific[w.Provides] || specific[w.Provides] && w.ProvidesForPlatform == ws.NeedsForPlatform {
				w.Next = append(w.Next, ws.Name)
			}
		}
	}
	return checkWorkflowSanity(workers)
}

// checkWorkflowSanity checks if the workflow is a tree.
//
// A sane workflow has one path to each worker and includes all workers.
// Multiple paths could mean multiple predecessors to a worker, or could be a circularity.
func checkWorkflowSanity(workers []*admin.Worker) error {
	var roots []*admin.Worker
	m := map[string]*admin.Worker{}
	for _, w := range workers {
		if w.Needs == tricium.Data_GIT_FILE_DETAILS {
			roots = append(roots, w)
		}
		m[w.Name] = w
	}
	visited := map[string]*admin.Worker{}
	for _, w := range roots {
		if err := checkWorkerDeps(w, m, visited); err != nil {
			return err
		}
	}
	if len(visited) < len(workers) {
		return errors.New("non-accessible workers in workflow")
	}
	return nil
}

// checkWorkerDeps detects joined/circular deps and unknown successors.
//
// Deps are recursively followed via Next pointers for the provided worker.
// The provided visited map is used to track already visited workers to detect
// multiple paths to a worker.
func checkWorkerDeps(w *admin.Worker, m map[string]*admin.Worker, visited map[string]*admin.Worker) error {
	if _, ok := visited[w.Name]; ok {
		return fmt.Errorf("multiple paths to worker %s", w.Name)
	}
	visited[w.Name] = w
	for _, n := range w.Next {
		wn, ok := m[n]
		if !ok {
			return fmt.Errorf("unknown next worker %s", n)
		}
		if err := checkWorkerDeps(wn, m, visited); err != nil {
			return err
		}
	}
	return nil
}

// includeFunction checks if the provided function should be included based on the provided paths.
//
// The paths are checked against the path filters included for the function. If there are no
// path filters, or no paths, then the function is included without further checking.
// With both paths and path filters, there needs to be at least one path match for the function to
// be included.
// Note that path filters are only provided for analyzers.
func includeFunction(f *tricium.Function, paths []string) (bool, error) {
	if f.Type == tricium.Function_ISOLATOR || len(paths) == 0 || f.PathFilters == nil || len(f.PathFilters) == 0 {
		return true, nil
	}
	for _, p := range paths {
		for _, filter := range f.PathFilters {
			ok, err := filepath.Match(filter, p)
			if err != nil {
				return false, fmt.Errorf("failed to check path filter %s for path %s", filter, p)
			}
			if ok {
				return true, nil
			}
		}
	}
	return false, nil
}

// createWorker creates a worker from the provided function, selection and service config.
//
// The provided function is assumed to be verified.
func createWorker(s *tricium.Selection, sc *tricium.ServiceConfig, f *tricium.Function) (*admin.Worker, error) {
	i := tricium.LookupImplForPlatform(f, s.Platform) // if verified, there should be an impl.
	p := tricium.LookupPlatform(sc, s.Platform)       // if verified, the platform should be known.
	// TODO(emso): Consider composing worker names using a character not allowed in function/platform names, e.g., '/'.
	w := &admin.Worker{
		Name:                fmt.Sprintf("%s_%s", s.Function, s.Platform),
		Needs:               f.Needs,
		Provides:            f.Provides,
		NeedsForPlatform:    i.NeedsForPlatform,
		ProvidesForPlatform: i.ProvidesForPlatform,
		RuntimePlatform:     i.RuntimePlatform,
		Dimensions:          p.Dimensions,
		CipdPackages:        i.CipdPackages,
		Deadline:            i.Deadline,
	}
	switch ii := i.Impl.(type) {
	case *tricium.Impl_Recipe:
		rps, err := tricium.GetRecipePackages(sc, s.Platform)
		if err != nil {
			return nil, errors.New("failed to lookup service recipe packages")
		}
		w.CipdPackages = append(w.CipdPackages, rps...)
		w.Cmd, err = tricium.GetRecipeCmd(sc, s.Platform)
		if err != nil {
			return nil, errors.New("failed to lookup service recipe command")
		}
		p := map[string]interface{}{}
		for _, prop := range ii.Recipe.Properties {
			p[prop.Key] = prop.Value
		}
		for _, c := range s.Configs {
			p[c.Name] = c.Value
		}
		b, err := json.Marshal(p)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal recipe properties: %v", err)
		}
		// TODO(emso): improve the command composition
		w.Cmd.Args = append(w.Cmd.Args, []string{
			"--recipe", ii.Recipe.Path,
			"--repository", ii.Recipe.Repository,
			"--revision", ii.Recipe.Revision,
			"--properties", string(b)}...)
	case *tricium.Impl_Cmd:
		w.Cmd = ii.Cmd
		for _, c := range s.Configs {
			w.Cmd.Args = append(w.Cmd.Args, "--"+c.Name, c.Value)
		}
	case nil:
		return nil, fmt.Errorf("missing impl when constructing worker %s", w.Name)
	default:
		return nil, fmt.Errorf("Impl.Impl has unexpected type %T", ii)
	}
	return w, nil
}
