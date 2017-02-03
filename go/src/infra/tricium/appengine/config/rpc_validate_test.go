// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/v1"
)

func TestFlatten(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("Flattens implementation fields", func() {
			p1 := "Linux-32"
			p2 := "Linux-64"
			analyzers := []*tricium.Analyzer{
				{
					Impls: []*tricium.Impl{
						{
							Platforms: []string{
								p1,
								p2,
							},
							Cmd: &tricium.Cmd{
								Exec: "echo",
								Args: []string{
									"hello",
								},
							},
							Deadline: 3200,
						},
					},
				},
			}
			flatten(analyzers)
			So(len(analyzers[0].Impls), ShouldEqual, 2)
			So(len(analyzers[0].Impls[0].Platforms), ShouldEqual, 1)
			So(len(analyzers[0].Impls[1].Platforms), ShouldEqual, 1)
			So(analyzers[0].Impls[0].Platforms[0], ShouldEqual, p1)
			So(analyzers[0].Impls[1].Platforms[0], ShouldEqual, p2)
		})
	})
}

func TestMerge(t *testing.T) {
	Convey("Test Environment", t, func() {

		analyzer := "PyLint"
		platform := "Win"
		config := "enable"
		sd := &tricium.ServiceConfig{
			Platforms: []*tricium.Platform{
				{
					Name: platform,
				},
			},
		}
		analyzers := []*tricium.Analyzer{
			{
				Name:     analyzer,
				Needs:    tricium.Data_FILES,
				Provides: tricium.Data_RESULTS,
				Impls: []*tricium.Impl{
					{
						Platforms: []string{platform},
						Deadline:  120,
					},
				},
				ConfigDefs: []*tricium.ConfigDef{
					{
						Name: config,
					},
				},
			},
		}

		Convey("Supported analyzer platform OK", func() {
			_, err := merge(sd, &tricium.ProjectConfig{
				Analyzers: analyzers,
				Selections: []*tricium.Selection{
					{
						Analyzer: analyzer,
						Platform: platform,
					},
				},
			})
			So(err, ShouldBeNil)
		})

		Convey("Non-supported analyzer platform causes error", func() {
			_, err := merge(sd, &tricium.ProjectConfig{
				Analyzers: analyzers,
				Selections: []*tricium.Selection{
					{
						Analyzer: analyzer,
						Platform: "blabla",
					},
				},
			})
			So(err, ShouldNotBeNil)
		})

		Convey("Supported analyzer config OK", func() {
			_, err := merge(sd, &tricium.ProjectConfig{
				Analyzers: analyzers,
				Selections: []*tricium.Selection{
					{
						Analyzer: analyzer,
						Platform: platform,
						Configs: []*tricium.Config{
							{
								Name:  config,
								Value: "all",
							},
						},
					},
				},
			})
			So(err, ShouldBeNil)
		})

		Convey("Non-supported analyzer config causes error", func() {
			_, err := merge(sd, &tricium.ProjectConfig{
				Analyzers: analyzers,
				Selections: []*tricium.Selection{
					{
						Analyzer: analyzer,
						Platform: platform,
						Configs: []*tricium.Config{
							{
								Name:  "blabla",
								Value: "all",
							},
						},
					},
				},
			})
			So(err, ShouldNotBeNil)
		})
	})
}

func TestMergeAnalyzers(t *testing.T) {
	Convey("Test Environment", t, func() {

		analyzer := "PyLint"
		platform := "Win"
		sc := &tricium.ServiceConfig{
			Platforms: []*tricium.Platform{
				{
					Name: platform,
				},
			},
		}

		Convey("Project analyzer def without service def must have data deps", func() {
			_, err := mergeAnalyzers(analyzer, sc, nil, &tricium.Analyzer{Name: analyzer})
			So(err, ShouldNotBeNil)
		})

		Convey("Service analyzer def must have data deps", func() {
			_, err := mergeAnalyzers(analyzer, sc, &tricium.Analyzer{Name: analyzer}, nil)
			So(err, ShouldNotBeNil)
		})

		Convey("No service analyzer config is OK", func() {
			_, err := mergeAnalyzers(analyzer, sc, nil, &tricium.Analyzer{
				Name:     analyzer,
				Needs:    tricium.Data_FILES,
				Provides: tricium.Data_RESULTS,
			})
			So(err, ShouldBeNil)
		})

		Convey("No project analyzer config is OK", func() {
			_, err := mergeAnalyzers(analyzer, sc, &tricium.Analyzer{
				Name:     analyzer,
				Needs:    tricium.Data_FILES,
				Provides: tricium.Data_RESULTS,
			}, nil)
			So(err, ShouldBeNil)
		})

		Convey("Change of service data deps not allowed", func() {
			_, err := mergeAnalyzers(analyzer, sc, &tricium.Analyzer{
				Name:     analyzer,
				Needs:    tricium.Data_FILES,
				Provides: tricium.Data_RESULTS,
			}, &tricium.Analyzer{
				Name:     analyzer,
				Provides: tricium.Data_CLANG_DETAILS,
			})
			So(err, ShouldNotBeNil)
		})

		Convey("Neither service nor analyzer config not OK", func() {
			_, err := mergeAnalyzers(analyzer, sc, nil, nil)
			So(err, ShouldNotBeNil)
		})

		Convey("Project details override service details", func() {
			user := "someone"
			comp := "someonesComp"
			exec := "cat"
			deadline := int32(120)
			a, err := mergeAnalyzers(analyzer, sc, &tricium.Analyzer{
				Name:        analyzer,
				Needs:       tricium.Data_FILES,
				Provides:    tricium.Data_RESULTS,
				PathFilters: []string{"*\\.py", "*\\.pypy"},
				Owner:       "emso",
				Component:   "compA",
				Impls: []*tricium.Impl{
					{
						Platforms: []string{platform},
						Cmd: &tricium.Cmd{
							Exec: "echo",
						},
						Deadline: 60,
					},
				},
			}, &tricium.Analyzer{
				Name:        analyzer,
				PathFilters: []string{"*\\.py"},
				Owner:       user,
				Component:   comp,
				Impls: []*tricium.Impl{
					{
						Platforms: []string{platform},
						Cmd: &tricium.Cmd{
							Exec: exec,
						},
						Deadline: deadline,
					},
				},
			})
			So(err, ShouldBeNil)
			So(a, ShouldNotBeNil)
			So(a.Owner, ShouldEqual, user)
			So(a.Component, ShouldEqual, comp)
			So(len(a.PathFilters), ShouldEqual, 1)
			So(len(a.Impls), ShouldEqual, 1)
			So(len(a.Impls[0].Platforms), ShouldEqual, 1)
			So(a.Impls[0].Platforms[0], ShouldEqual, platform)
			So(a.Impls[0].Cmd.Exec, ShouldEqual, exec)
			So(a.Impls[0].Deadline, ShouldEqual, deadline)
		})
	})
}

func TestMergeConfigDefs(t *testing.T) {
	Convey("Test Environment", t, func() {
		scd := []*tricium.ConfigDef{
			{
				Name: "optA",
			},
			{
				Name: "optB",
			},
		}
		pcd := []*tricium.ConfigDef{
			{
				Name: "optB",
			},
			{
				Name: "optC",
			},
		}
		Convey("Merges config def with override", func() {
			mcd := mergeConfigDefs(scd, pcd)
			So(len(mcd), ShouldEqual, 3)
		})
	})
}

func TestMergeImpls(t *testing.T) {
	Convey("Test Environment", t, func() {
		si := []*tricium.Impl{
			{
				Platforms: []string{"Linux"},
			},
			{
				Platforms: []string{"Win"},
			},
		}
		pi := []*tricium.Impl{
			{
				Platforms: []string{"Win"},
			},
			{
				Platforms: []string{"Mac"},
			},
		}
		Convey("Merges impls with override", func() {
			mi := mergeImpls(si, pi)
			So(len(mi), ShouldEqual, 3)
		})
	})
}

// TODO(emso): test checks
