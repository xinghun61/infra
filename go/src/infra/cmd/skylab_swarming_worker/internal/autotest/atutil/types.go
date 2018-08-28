// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package atutil

import (
	"infra/cmd/skylab_swarming_worker/internal/autotest"
)

// MainJob describes the overall job, which dictates certain job
// global settings for running autoserv.
type MainJob struct {
	AutotestConfig   autotest.Config
	ResultsDir       string
	UseLocalHostInfo bool
}

// AutoservJob describes the interface a job object needs to be passed
// to RunAutoserv.
type AutoservJob interface {
	AutoservArgs() *autotest.AutoservArgs
}

type keyvalsJob interface {
	JobKeyvals() map[string]string
}

// AdminTaskType is an enum used in AdminTask to determine what type
// of admin task to run.
type AdminTaskType int

// Task constants.
const (
	// NoTask can be used as a null AdminTaskType value.
	NoTask AdminTaskType = iota
	Verify
	Cleanup
	Reset
	Repair
)

//go:generate stringer -type=AdminTaskType

// HostInfoSubDir is the filename of the directory for storing host info.
//
// TODO(ayatane): Move this elsewhere.
const HostInfoSubDir = "host_info_store"

var _ AutoservJob = &AdminTask{}

// AdminTask represents an admin task to run.  AdminTask implements AutoservJob.
type AdminTask struct {
	Type       AdminTaskType
	Host       string
	ResultsDir string
}

// AutoservArgs returns the AutoservArgs for the task.
func (t *AdminTask) AutoservArgs() *autotest.AutoservArgs {
	a := &autotest.AutoservArgs{
		HostInfoSubDir:    HostInfoSubDir,
		Hosts:             []string{t.Host},
		Lab:               true,
		LocalOnlyHostInfo: true,
		ResultsDir:        t.ResultsDir,
		WritePidfile:      true,
	}
	switch t.Type {
	case Verify:
		a.Verify = true
	case Cleanup:
		a.Cleanup = true
	case Reset:
		a.Reset = true
	case Repair:
		a.Repair = true
	}
	return a
}

var _ AutoservJob = &Provision{}

// Provision represents a provision task to run.  Provision implements
// AutoservJob.
type Provision struct {
	Host              string
	Labels            []string
	LocalOnlyHostInfo bool
	ResultsDir        string
}

// AutoservArgs returns the AutoservArgs for the task.
func (p *Provision) AutoservArgs() *autotest.AutoservArgs {
	return &autotest.AutoservArgs{
		HostInfoSubDir:    HostInfoSubDir,
		Hosts:             []string{p.Host},
		JobLabels:         p.Labels,
		Lab:               true,
		LocalOnlyHostInfo: p.LocalOnlyHostInfo,
		Provision:         true,
		ResultsDir:        p.ResultsDir,
		WritePidfile:      true,
	}
}

var _ AutoservJob = &HostlessTest{}
var _ keyvalsJob = &HostlessTest{}

// HostlessTest represents a hostless test to run.  HostlessTest
// implements AutoservJob.
type HostlessTest struct {
	ClientTest   bool
	ControlFile  string
	ControlName  string
	ExecutionTag string
	Keyvals      map[string]string
	Name         string
	Owner        string
	ResultsDir   string
	TestRetries  int
}

// AutoservArgs returns the AutoservArgs for the task.
func (t *HostlessTest) AutoservArgs() *autotest.AutoservArgs {
	return &autotest.AutoservArgs{
		ClientTest:   t.ClientTest,
		ControlFile:  t.ControlFile,
		ControlName:  t.ControlName,
		ExecutionTag: t.ExecutionTag,
		JobName:      t.Name,
		JobOwner:     t.Owner,
		Lab:          true,
		NoTee:        true,
		ResultsDir:   t.ResultsDir,
		TestRetries:  t.TestRetries,
		WritePidfile: true,
	}
}

// JobKeyvals returns the keyvals for the task.
func (t *HostlessTest) JobKeyvals() map[string]string {
	return t.Keyvals
}

var _ AutoservJob = &HostTest{}
var _ keyvalsJob = &HostTest{}

// HostTest represents a host test to run.  HostTest implements AutoservJob.
type HostTest struct {
	HostlessTest
	Hosts             []string
	LocalOnlyHostInfo bool
	ParentJobID       int
	RequireSSP        bool
	TestSourceBuild   string
}

// AutoservArgs returns the AutoservArgs for the task.
func (t *HostTest) AutoservArgs() *autotest.AutoservArgs {
	args := t.HostlessTest.AutoservArgs()
	args.HostInfoSubDir = HostInfoSubDir
	args.Hosts = t.Hosts
	args.LocalOnlyHostInfo = t.LocalOnlyHostInfo
	args.ParentJobID = t.ParentJobID
	args.RequireSSP = t.RequireSSP
	args.TestSourceBuild = t.TestSourceBuild
	args.VerifyJobRepoURL = true
	return args
}

// Result contains information about RunAutoserv results.
type Result struct {
	Aborted bool
	// Exit is the exit status for the autoserv command, if
	// autoserv was run.
	Exit        int
	TestsFailed int
	// Started is true if the autoserv process was started
	// successfully.
	Started bool
}

// Success returns true if autoserv exited with 0 and no tests failed.
func (r *Result) Success() bool {
	return r.Exit == 0 && r.TestsFailed == 0
}
