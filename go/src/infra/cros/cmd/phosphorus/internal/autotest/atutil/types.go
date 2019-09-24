// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package atutil

import (
	"infra/cros/cmd/phosphorus/internal/autotest"
	"infra/cros/cmd/phosphorus/internal/osutil"
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

const (
	// NoTask can be used as a null AdminTaskType value.
	NoTask AdminTaskType = iota
	// Verify represents `autoserv -v`.
	Verify
	// Cleanup represents `autoserv --cleanup`.
	Cleanup
	// Reset represents `autoserv --reset`.
	Reset
	// Repair represents `autoserv -R`.
	Repair
)

//go:generate stringer -type=AdminTaskType

const hostInfoSubDir = "host_info_store"

var _ AutoservJob = &AdminTask{}

// AdminTask represents an admin task to run.  AdminTask implements AutoservJob.
type AdminTask struct {
	Type       AdminTaskType
	Host       string
	ResultsDir string
}

// AutoservArgs represents the CLI args for `autoserv`.
func (t *AdminTask) AutoservArgs() *autotest.AutoservArgs {
	a := &autotest.AutoservArgs{
		HostInfoSubDir:    hostInfoSubDir,
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

// AutoservArgs represents the CLI args for `autoserv`.
func (p *Provision) AutoservArgs() *autotest.AutoservArgs {
	return &autotest.AutoservArgs{
		HostInfoSubDir:    hostInfoSubDir,
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
	Args         string
	ClientTest   bool
	ControlFile  string
	ControlName  string
	ExecutionTag string
	Keyvals      map[string]string
	Name         string
	Owner        string
	ResultsDir   string
}

// AutoservArgs represents the CLI args for `autoserv`.
func (t *HostlessTest) AutoservArgs() *autotest.AutoservArgs {
	a := autotest.AutoservArgs{
		Args:         t.Args,
		ClientTest:   t.ClientTest,
		ControlFile:  t.ControlFile,
		ControlName:  t.ControlName,
		ExecutionTag: t.ExecutionTag,
		JobName:      t.Name,
		JobOwner:     t.Owner,
		Lab:          true,
		NoTee:        true,
		ResultsDir:   t.ResultsDir,
		WritePidfile: true,
	}
	return &a
}

// JobKeyvals returns the autotest keyvals.
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

// AutoservArgs represents the CLI args for `autoserv`.
func (t *HostTest) AutoservArgs() *autotest.AutoservArgs {
	args := t.HostlessTest.AutoservArgs()
	args.HostInfoSubDir = hostInfoSubDir
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
	osutil.RunResult
	// Exit is the exit status for the autoserv command, if
	// autoserv was run.
	Exit        int
	TestsFailed int
}

// Success returns true if autoserv exited with 0 and no tests failed.
func (r *Result) Success() bool {
	return r.Exit == 0 && r.TestsFailed == 0
}
