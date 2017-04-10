// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	admin "infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
)

const (
	project  = "test-project"
	pylint   = "PyLint"
	mylint   = "MyLint"
	isolator = "isolator"
	platform = tricium.Platform_UBUNTU
)

var (
	sc = &tricium.ServiceConfig{
		SwarmingServer: "chromium-swarm-dev",
		IsolateServer:  "isolatedserver-dev",
		Projects: []*tricium.ProjectDetails{
			{
				Name: project,
				SwarmingServiceAccount: "swarming@email.com",
			},
		},
		Platforms: []*tricium.Platform_Details{
			{
				Name:       platform,
				Dimensions: []string{"pool:Chrome", "os:Ubuntu13.04"},
				HasRuntime: true,
			},
		},
		DataDetails: []*tricium.Data_TypeDetails{
			{
				Type:               tricium.Data_GIT_FILE_DETAILS,
				IsPlatformSpecific: false,
			},
			{
				Type:               tricium.Data_FILES,
				IsPlatformSpecific: false,
			},
			{
				Type:               tricium.Data_CLANG_DETAILS,
				IsPlatformSpecific: true,
			},
			{
				Type:               tricium.Data_RESULTS,
				IsPlatformSpecific: true,
			},
		},
		Analyzers: []*tricium.Analyzer{
			{
				Name:     pylint,
				Needs:    tricium.Data_FILES,
				Provides: tricium.Data_RESULTS,
				Impls: []*tricium.Impl{
					{
						ProvidesForPlatform: platform,
						RuntimePlatform:     platform,
						Impl: &tricium.Impl_Cmd{
							Cmd: &tricium.Cmd{
								Exec: "pylint",
							},
						},
						Deadline: 120,
					},
				},
			},
		},
	}
)

func TestGenerate(t *testing.T) {
	Convey("Test Environment", t, func() {
		pc := &tricium.ProjectConfig{
			Name: project,
			Analyzers: []*tricium.Analyzer{
				{
					Name:     mylint,
					Needs:    tricium.Data_FILES,
					Provides: tricium.Data_RESULTS,
					Impls: []*tricium.Impl{
						{
							ProvidesForPlatform: platform,
							RuntimePlatform:     platform,
							Impl: &tricium.Impl_Cmd{
								Cmd: &tricium.Cmd{
									Exec: "mylint",
								},
							},
							Deadline: 199,
						},
					},
				},
				{
					Name:     isolator,
					Needs:    tricium.Data_GIT_FILE_DETAILS,
					Provides: tricium.Data_FILES,
					Impls: []*tricium.Impl{
						{
							ProvidesForPlatform: platform,
							RuntimePlatform:     platform,
							Impl: &tricium.Impl_Cmd{
								Cmd: &tricium.Cmd{
									Exec: "git-file-isolator",
								},
							},
							Deadline: 499,
						},
					},
				},
			},
			Selections: []*tricium.Selection{
				{
					Analyzer: isolator,
					Platform: platform,
				},
				{
					Analyzer: pylint,
					Platform: platform,
				},
				{
					Analyzer: mylint,
					Platform: platform,
				},
			},
		}
		Convey("correct selection generates workflow", func() {
			wf, err := Generate(sc, pc, []string{})
			So(err, ShouldBeNil)
			So(len(wf.Workers), ShouldEqual, 3)
		})
	})
}

func TestCheckWorkflowSanity(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("correct workflow is sane", func() {
			w := []*admin.Worker{
				{
					Name:  "FileIsolator",
					Needs: tricium.Data_GIT_FILE_DETAILS,
					Next:  []string{"PyLint"},
				},
				{
					Name: "PyLint",
				},
			}
			err := checkWorkflowSanity(w)
			So(err, ShouldBeNil)
		})
		Convey("non-accessible workers cause error", func() {
			w := []*admin.Worker{
				{
					Name:  "FileIsolator",
					Needs: tricium.Data_GIT_FILE_DETAILS,
				},
				{
					Name: "PyLint",
				},
			}
			err := checkWorkflowSanity(w)
			So(err, ShouldNotBeNil)
		})
	})
}

func TestFollowWorkerDeps(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("circular dep causes error", func() {
			visited := map[string]*admin.Worker{}
			workers := map[string]*admin.Worker{}
			w := &admin.Worker{
				Name:  "FileIsolator",
				Needs: tricium.Data_GIT_FILE_DETAILS,
				Next:  []string{"FileIsolator"},
			}
			workers[w.Name] = w
			err := checkWorkerDeps(w, workers, visited)
			So(err, ShouldNotBeNil)
		})
		Convey("multiple paths to worker causes error", func() {
			visited := map[string]*admin.Worker{}
			workers := map[string]*admin.Worker{}
			w := &admin.Worker{
				Name:  "FileIsolator",
				Needs: tricium.Data_GIT_FILE_DETAILS,
				Next:  []string{"PyLint"},
			}
			w2 := &admin.Worker{
				Name:  "PyLint",
				Needs: tricium.Data_FILES,
			}
			w3 := &admin.Worker{
				Name:  "FileIsolator2",
				Needs: tricium.Data_GIT_FILE_DETAILS,
				Next:  []string{"PyLint"},
			}
			workers[w.Name] = w
			workers[w2.Name] = w2
			workers[w3.Name] = w3
			err := checkWorkerDeps(w, workers, visited)
			So(err, ShouldBeNil)
			err = checkWorkerDeps(w3, workers, visited)
			So(err, ShouldNotBeNil)
		})
		Convey("ok deps render no error", func() {
			visited := map[string]*admin.Worker{}
			workers := map[string]*admin.Worker{}
			w := &admin.Worker{
				Name:  "FileIsolator",
				Needs: tricium.Data_GIT_FILE_DETAILS,
				Next:  []string{"PyLint", "GoLint"},
			}
			w2 := &admin.Worker{
				Name:  "PyLint",
				Needs: tricium.Data_FILES,
			}
			w3 := &admin.Worker{
				Name:  "GoLint",
				Needs: tricium.Data_FILES,
			}
			workers[w.Name] = w
			workers[w2.Name] = w2
			workers[w3.Name] = w3
			err := checkWorkerDeps(w, workers, visited)
			So(err, ShouldBeNil)
		})
	})
}

func TestIncludeAnalyzer(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("No paths means analyzer is included", func() {
			ok, err := includeAnalyzer(&tricium.Analyzer{}, nil)
			So(err, ShouldBeNil)
			So(ok, ShouldBeTrue)
		})
		Convey("No file paths means analyzer is included", func() {
			ok, err := includeAnalyzer(&tricium.Analyzer{}, []string{"README.md"})
			So(err, ShouldBeNil)
			So(ok, ShouldBeTrue)
		})
		Convey("Analyzer is included when path matches filter", func() {
			ok, err := includeAnalyzer(&tricium.Analyzer{
				PathFilters: []string{"*.md"},
			}, []string{"README.md"})
			So(err, ShouldBeNil)
			So(ok, ShouldBeTrue)
		})
		Convey("Analyzer is not included when there is no match", func() {
			ok, err := includeAnalyzer(&tricium.Analyzer{
				PathFilters: []string{"*.md"},
			}, []string{"file.cpp"})
			So(err, ShouldBeNil)
			So(ok, ShouldBeFalse)
		})
	})
}

func TestCreateWorker(t *testing.T) {
	Convey("Test Environment", t, func() {
		platform := tricium.Platform_UBUNTU
		analyzer := "PyLint"
		config := "enable"
		configValue := "all"
		selection := &tricium.Selection{
			Analyzer: analyzer,
			Platform: platform,
			Configs: []*tricium.Config{
				{
					Name:  config,
					Value: configValue,
				},
			},
		}
		dimension := "pool:Default"
		sc := &tricium.ServiceConfig{
			Platforms: []*tricium.Platform_Details{
				{
					Name:       platform,
					Dimensions: []string{dimension},
				},
			},
			RecipePackages: []*tricium.CipdPackage{
				{
					PackageName: "infra/tools/luci/kitchen",
					Path:        ".",
					Version:     "git_revision:e6b225b4b008e57014021ad2c2e92b5e3f499438",
				},
			},
			RecipeCmd: &tricium.Cmd{
				Exec: "kitchen",
				Args: []string{
					"cook",
				},
			},
		}
		deadline := int32(120)
		Convey("Correctly creates cmd-based worker", func() {
			a := &tricium.Analyzer{
				Name:       analyzer,
				Needs:      tricium.Data_FILES,
				Provides:   tricium.Data_RESULTS,
				ConfigDefs: []*tricium.ConfigDef{{Name: config}},
				Impls: []*tricium.Impl{
					{
						ProvidesForPlatform: platform,
						RuntimePlatform:     platform,
						CipdPackages: []*tricium.CipdPackage{
							{
								PackageName: "package",
								Path:        "path/to/folder",
								Version:     "git-revision:abcdefg",
							},
						},
						Impl: &tricium.Impl_Cmd{
							Cmd: &tricium.Cmd{
								Exec: "pylint",
							},
						},
						Deadline: deadline,
					},
				},
			}
			w, err := createWorker(selection, sc, a)
			So(err, ShouldBeNil)
			So(w.Name, ShouldEqual, fmt.Sprintf("%s_%s", analyzer, platform))
			So(w.Needs, ShouldEqual, a.Needs)
			So(w.Provides, ShouldEqual, a.Provides)
			So(w.ProvidesForPlatform, ShouldEqual, platform)
			So(len(w.Dimensions), ShouldEqual, 1)
			So(w.Dimensions[0], ShouldEqual, dimension)
			So(len(w.CipdPackages), ShouldEqual, 1)
			So(w.Deadline, ShouldEqual, deadline)
			So(len(w.Cmd.Args), ShouldEqual, 2)
			So(w.Cmd.Args[0], ShouldEqual, fmt.Sprintf("--%s", config))
			So(w.Cmd.Args[1], ShouldEqual, configValue)
		})

		Convey("Correctly creates recipe-based worker", func() {
			recipe := "recipe"
			repo := "infra-repo"
			rev := "abcdefg"
			a := &tricium.Analyzer{
				Name:       analyzer,
				Needs:      tricium.Data_FILES,
				Provides:   tricium.Data_RESULTS,
				ConfigDefs: []*tricium.ConfigDef{{Name: config}},
				Impls: []*tricium.Impl{
					{
						ProvidesForPlatform: platform,
						RuntimePlatform:     platform,
						CipdPackages: []*tricium.CipdPackage{
							{
								PackageName: "package",
								Path:        "path/to/folder",
								Version:     "git-revision:abcdefg",
							},
						},
						Impl: &tricium.Impl_Recipe{
							Recipe: &tricium.Recipe{
								Repository: repo,
								Path:       recipe,
								Revision:   rev,
							},
						},
						Deadline: deadline,
					},
				},
			}
			w, err := createWorker(selection, sc, a)
			So(err, ShouldBeNil)
			So(w.Name, ShouldEqual, fmt.Sprintf("%s_%s", analyzer, platform))
			So(w.Needs, ShouldEqual, a.Needs)
			So(w.Provides, ShouldEqual, a.Provides)
			So(w.ProvidesForPlatform, ShouldEqual, platform)
			So(len(w.Dimensions), ShouldEqual, 1)
			So(w.Dimensions[0], ShouldEqual, dimension)
			So(len(w.CipdPackages), ShouldEqual, 2)
			So(w.Deadline, ShouldEqual, deadline)
			// kitchen cook --recipe ... --repository ... --revision ... --properties {config:configValue}
			So(w.Cmd.Exec, ShouldEqual, "kitchen")
			So(len(w.Cmd.Args), ShouldEqual, 9)
			So(w.Cmd.Args[0], ShouldEqual, "cook")
			So(w.Cmd.Args[1], ShouldEqual, "--recipe")
			So(w.Cmd.Args[2], ShouldEqual, recipe)
			So(w.Cmd.Args[3], ShouldEqual, "--repository")
			So(w.Cmd.Args[4], ShouldEqual, repo)
			So(w.Cmd.Args[5], ShouldEqual, "--revision")
			So(w.Cmd.Args[6], ShouldEqual, rev)
			So(w.Cmd.Args[7], ShouldEqual, "--properties")
			So(w.Cmd.Args[8], ShouldEqual, fmt.Sprintf("{\"%s\":\"%s\"}", config, configValue))
		})
	})
}

func TestResolveSuccessorWorkers(t *testing.T) {
	Convey("Test Environment", t, func() {
		linux := tricium.Platform_UBUNTU
		win := tricium.Platform_WINDOWS
		fiLinux := "FileIsolator_Ubuntu"
		pyLinux := "PyLint_Ubuntu"
		ciLinux := "ClangIsolator_Ubuntu"
		ciWin := "ClangIsolator_Win"
		ctLinux := "ClangTidy_Ubuntu"
		ctWin := "ClangTidy_Win"
		Convey("Connects simple data types correctly", func() {
			w := []*admin.Worker{
				{
					Name:            fiLinux,
					Needs:           tricium.Data_GIT_FILE_DETAILS,
					Provides:        tricium.Data_FILES,
					RuntimePlatform: linux,
				},
				{
					Name:                pyLinux,
					Needs:               tricium.Data_FILES,
					Provides:            tricium.Data_RESULTS,
					ProvidesForPlatform: linux,
					RuntimePlatform:     linux,
				},
			}
			resolveSuccessorWorkers(sc, w)
			So(len(w[0].Next), ShouldEqual, 1)
			So(w[0].Next[0], ShouldEqual, pyLinux)
		})
		Convey("Connects platform types correctly", func() {
			w := []*admin.Worker{
				{
					Name:     fiLinux,
					Needs:    tricium.Data_GIT_FILE_DETAILS,
					Provides: tricium.Data_FILES,
				},
				{
					Name:                ciLinux,
					Needs:               tricium.Data_FILES,
					Provides:            tricium.Data_CLANG_DETAILS,
					ProvidesForPlatform: linux,
				},
				{
					Name:                ciWin,
					Needs:               tricium.Data_FILES,
					Provides:            tricium.Data_CLANG_DETAILS,
					ProvidesForPlatform: win,
				},
				{
					Name:                ctLinux,
					Needs:               tricium.Data_CLANG_DETAILS,
					NeedsForPlatform:    linux,
					Provides:            tricium.Data_RESULTS,
					ProvidesForPlatform: linux,
				},
				{
					Name:                ctWin,
					Needs:               tricium.Data_CLANG_DETAILS,
					NeedsForPlatform:    win,
					Provides:            tricium.Data_RESULTS,
					ProvidesForPlatform: win,
				},
			}
			resolveSuccessorWorkers(sc, w)
			// fi_liux -> ci_linux -> ct_linux
			//         -> ci_win -> ct_win
			So(len(w[0].Next), ShouldEqual, 2) // fi_linux
			So(w[0].Next[0], ShouldEqual, ciLinux)
			So(w[0].Next[1], ShouldEqual, ciWin)
			So(len(w[1].Next), ShouldEqual, 1) // ci_linux
			So(w[1].Next[0], ShouldEqual, ctLinux)
			So(len(w[2].Next), ShouldEqual, 1) // ci_win
			So(w[2].Next[0], ShouldEqual, ctWin)
			So(len(w[3].Next), ShouldEqual, 0) // ct_linux
			So(len(w[4].Next), ShouldEqual, 0) // ct_win
		})
	})
}
