// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"bytes"
	"errors"
	"fmt"
	"path/filepath"

	"github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
)

func (*configServer) GenerateWorkflow(c context.Context, req *admin.GenerateWorkflowRequest) (*admin.GenerateWorkflowResponse, error) {
	if req.Project == "" {
		return nil, grpc.Errorf(codes.InvalidArgument, "missing project name")
	}
	wf, err := generate(c, req, &common.LuciConfigProvider{})
	if err != nil {
		return nil, grpc.Errorf(codes.Internal, "failed to validate config")
	}
	return &admin.GenerateWorkflowResponse{Workflow: wf}, nil
}

// generate generates a Tricium workflow based on the provided request.
//
// The workflow will be computed from the validated and merged config for the project in question,
// and we filtered to only include workers relevant to the files to be analyzed.
func generate(c context.Context, req *admin.GenerateWorkflowRequest, cp common.ConfigProvider) (*admin.Workflow, error) {
	pc, err := cp.GetProjectConfig(c, req.Project)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to get project config: %v", err)
		return nil, err
	}
	vpc, err := validate(c, &admin.ValidateRequest{ProjectConfig: pc}, cp)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to validate project config: %v", err)
		return nil, err
	}
	sc, err := cp.GetServiceConfig(c)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to get service config: %v", err)
		return nil, err
	}
	var workers []*admin.Worker
	analyzers := make(map[string]*tricium.Analyzer)
	for _, s := range vpc.Selections {
		_, ok := analyzers[s.Analyzer]
		if !ok {
			a, err := tricium.LookupProjectAnalyzer(vpc, s.Analyzer)
			if err != nil {
				logging.WithError(err).Errorf(c, "failed to lookup project analyzer: %v", err)
				return nil, err
			}
			analyzers[s.Analyzer] = a
		}
		ok, err = includeAnalyzer(analyzers[s.Analyzer], req.GetPaths())
		if err != nil {
			logging.WithError(err).Errorf(c, "failed include analyzer check: %v", err)
			return nil, err
		}
		if ok {
			w, err := createWorker(s, sc, analyzers[s.Analyzer])
			if err != nil {
				logging.WithError(err).Errorf(c, "failed to create worker: %v", err)
				return nil, err
			}
			workers = append(workers, w)
		}
	}
	resolveSuccessorWorkers(sc, workers)
	err = checkWorkflowSanity(workers)
	if err != nil {
		logging.Errorf(c, "workflow is not sane: %v", err)
		return nil, err
	}
	return &admin.Workflow{Workers: workers}, nil
}

// checkWorkflowSanity checks if the workflow is sane.
//
// A sane workflow has one path to each worker and includes all workers.
// Multiple paths could mean multiple predecessors to a worker, or could be a circularity.
func checkWorkflowSanity(workers []*admin.Worker) error {
	var roots []*admin.Worker
	m := make(map[string]*admin.Worker)
	for _, w := range workers {
		if w.Needs == tricium.Data_GIT_FILE_DETAILS {
			roots = append(roots, w)
		}
		m[w.Name] = w
	}
	visited := make(map[string]*admin.Worker)
	for _, w := range roots {
		if err := followWorkerDeps(w, m, visited); err != nil {
			return err
		}
	}
	if len(visited) < len(workers) {
		return errors.New("non-accessible workers in workflow")
	}
	return nil
}

// followWorkerDeps recursively follows the Next pointers for the provided worker.
//
// The provided visited map is used to track already visited workers to detect
// multiple paths to a worker.
func followWorkerDeps(w *admin.Worker, m map[string]*admin.Worker, visited map[string]*admin.Worker) error {
	_, ok := visited[w.Name]
	if ok {
		return fmt.Errorf("multiple paths to worker %s", w.Name)
	}
	visited[w.Name] = w
	for _, n := range w.Next {
		wn, ok := m[n]
		if !ok {
			return fmt.Errorf("unknown next worker %s", n)
		}
		if err := followWorkerDeps(wn, m, visited); err != nil {
			return err
		}
	}
	return nil
}

// includeAnalyzer checks if the provided analyzer should be included based on the provided paths.
//
// The paths are checked against the path filters included for the analyzer. If there are no
// path filters, or no paths, then the analyzer is included without further checking.
// With both paths and path filters, there needs to be at least one path match for the analyzer to
// be included.
func includeAnalyzer(a *tricium.Analyzer, paths []string) (bool, error) {
	if paths == nil || len(paths) == 0 || a.PathFilters == nil || len(a.PathFilters) == 0 {
		return true, nil
	}
	for _, p := range paths {
		for _, f := range a.PathFilters {
			ok, err := filepath.Match(f, p)
			if err != nil {
				return false, fmt.Errorf("failed to check path filter %s for path %s", f, p)
			}
			if ok {
				return true, nil
			}
		}
	}
	return false, nil
}

// createWorker creates a worker from the provided analyzer, selection and service config.
//
// The provided analyzer is assumed to be verified.
func createWorker(s *tricium.Selection, sc *tricium.ServiceConfig, a *tricium.Analyzer) (*admin.Worker, error) {
	i := tricium.LookupImplForPlatform(a, s.Platform) // if verified, there should be an impl.
	p := tricium.LookupPlatform(sc, s.Platform)       // if verified, the platform should be known.
	// TODO(emso): Consider composing worker names using a character not allowed in analyzer/platform names, e.g., '/'.
	w := &admin.Worker{
		Name:                fmt.Sprintf("%s_%s", s.Analyzer, s.Platform.String()),
		Needs:               a.Needs,
		Provides:            a.Provides,
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
		var buffer bytes.Buffer
		buffer.WriteString("{")
		for _, prop := range ii.Recipe.Properties {
			buffer.WriteString(fmt.Sprintf("\"%s\": \"%s\",", prop.Key, prop.Value))
		}
		for _, c := range s.Configs {
			buffer.WriteString(fmt.Sprintf("\"%s\": \"%s\",", c.Name, c.Value))
		}
		buffer.WriteString("}")
		// TODO(emso): improve the command composition
		w.Cmd.Args = append(w.Cmd.Args, []string{
			"--recipe",
			ii.Recipe.Path,
			"--repository",
			ii.Recipe.Repository,
			"--revision",
			ii.Recipe.Revision,
			"--properties",
			buffer.String(),
		}...)
	case *tricium.Impl_Cmd:
		w.Cmd = ii.Cmd
		for _, c := range s.Configs {
			w.Cmd.Args = append(w.Cmd.Args,
				[]string{
					fmt.Sprintf("--%v", c.Name),
					c.Value,
				}...)
		}
	case nil:
		return nil, fmt.Errorf("missing impl when constructing worker %s", w.Name)

	default:
		return nil, fmt.Errorf("Impl.Impl has unexpected type %T", ii)
	}
	return w, nil
}

// resolveSuccessorWorkers computes successor workers based on data dependencies.
//
// The resulting list of successors are added to the Next fields of the provided workers.
// Platform-specific data types add an additional platform check to make successors of
// workers providing a platform-specific type only include successors running on that
// platform.
func resolveSuccessorWorkers(sc *tricium.ServiceConfig, workers []*admin.Worker) {
	specific := make(map[tricium.Data_Type]bool)
	for _, d := range sc.GetDataDetails() {
		specific[d.Type] = d.IsPlatformSpecific
	}
	needs := make(map[tricium.Data_Type][]*admin.Worker)
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
}
