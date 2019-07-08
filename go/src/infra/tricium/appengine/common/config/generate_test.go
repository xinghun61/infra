// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"encoding/json"
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	admin "infra/tricium/api/admin/v1"
	tricium "infra/tricium/api/v1"
)

const (
	project  = "test-project"
	pylint   = "PyLint"
	mylint   = "MyLint"
	isolator = "MyIsolator"
	platform = tricium.Platform_UBUNTU
)

var (
	sc = &tricium.ServiceConfig{
		BuildbucketServerHost: "cr-buildbucket-dev.appspot.com",
		IsolateServer:         "https://isolatedserver-dev.appspot.com",
		SwarmingServer:        "https://chromium-swarm-dev.appspot.com",
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
		Functions: []*tricium.Function{
			{
				Type:     tricium.Function_ANALYZER,
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

func fail(str string) {
	So(nil, func(a interface{}, b ...interface{}) string { return str }, nil)
}

func TestGenerate(t *testing.T) {
	Convey("Test Environment", t, func() {
		pc := &tricium.ProjectConfig{
			Functions: []*tricium.Function{
				{
					Type:     tricium.Function_ANALYZER,
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
					Type:     tricium.Function_ISOLATOR,
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
					Function: isolator,
					Platform: platform,
				},
				{
					Function: pylint,
					Platform: platform,
				},
				{
					Function: mylint,
					Platform: platform,
				},
			},
			SwarmingServiceAccount: "swarming@email.com",
		}
		Convey("Correct selection generates workflow", func() {
			wf, err := Generate(sc, pc, []*tricium.Data_File{}, "refs/1234/2", "https://chromium-review.googlesource.com/infra")
			So(err, ShouldBeNil)
			So(len(wf.Workers), ShouldEqual, 3)
		})
	})
}

func TestCheckWorkflowSanity(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("Correct workflow is sane", func() {
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
		Convey("Non-accessible workers cause error", func() {
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
		Convey("Circular dependencies causes error", func() {
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
		Convey("Multiple paths to worker causes error", func() {
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
		Convey("OK deps render no error", func() {
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

func TestIncludeFunction(t *testing.T) {
	Convey("No paths means function is included", t, func() {
		ok, err := includeFunction(&tricium.Function{
			Type:        tricium.Function_ANALYZER,
			PathFilters: []string{"*.cc", "*.cpp"},
		}, nil)
		So(err, ShouldBeNil)
		So(ok, ShouldBeTrue)
	})

	Convey("No path filters means function is included", t, func() {
		ok, err := includeFunction(&tricium.Function{
			Type: tricium.Function_ANALYZER,
		}, []*tricium.Data_File{
			{Path: "README.md"},
			{Path: "path/foo.cc"},
		})
		So(err, ShouldBeNil)
		So(ok, ShouldBeTrue)
	})

	Convey("Analyzer is included when any path matches filter", t, func() {
		ok, err := includeFunction(&tricium.Function{
			Type:        tricium.Function_ANALYZER,
			PathFilters: []string{"*.cc", "*.cpp"},
		}, []*tricium.Data_File{
			{Path: "README.md"},
			{Path: "path/foo.cc"},
		})
		So(err, ShouldBeNil)
		So(ok, ShouldBeTrue)
	})

	Convey("Analyzer function is not included when there is no match", t, func() {
		ok, err := includeFunction(&tricium.Function{
			Type:        tricium.Function_ANALYZER,
			PathFilters: []string{"*.cc", "*.cpp"},
		}, []*tricium.Data_File{
			{Path: "whitespace.txt"},
		})
		So(err, ShouldBeNil)
		So(ok, ShouldBeFalse)
	})

	Convey("Isolator function is included regardless of path match", t, func() {
		ok, err := includeFunction(&tricium.Function{
			Type:        tricium.Function_ISOLATOR,
			PathFilters: []string{"*.cc", "*.cpp"},
		}, []*tricium.Data_File{
			{Path: "README.md"},
			{Path: "path/foo.cc"},
		})
		So(err, ShouldBeNil)
		So(ok, ShouldBeTrue)
	})
}

func TestCreateWorker(t *testing.T) {
	Convey("Test Environment", t, func() {
		analyzer := "PyLint"
		config := "enable"
		configValue := "all"
		configJSON := "json"
		configValueJSON := "[\"one\",\"two\"]"
		gitRef := "refs/1234/2"
		gitURL := "https://chromium-review.googlesource.com/infra"
		selection := &tricium.Selection{
			Function: analyzer,
			Platform: platform,
			Configs: []*tricium.Config{
				{
					Name:      config,
					ValueType: &tricium.Config_Value{Value: configValue},
				},
				{
					Name:      configJSON,
					ValueType: &tricium.Config_ValueJ{ValueJ: configValueJSON},
				},
			},
		}
		dimension := "pool:Default"
		sc2 := &tricium.ServiceConfig{
			Platforms: []*tricium.Platform_Details{
				{
					Name:       platform,
					Dimensions: []string{dimension},
				},
			},
		}
		deadline := int32(120)
		Convey("Correctly creates cmd-based worker", func() {
			f := &tricium.Function{
				Name:       analyzer,
				Needs:      tricium.Data_FILES,
				Provides:   tricium.Data_RESULTS,
				ConfigDefs: []*tricium.ConfigDef{{Name: config}, {Name: configJSON}},
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
			w, err := createWorker(selection, sc2, f, gitRef, gitURL)
			So(err, ShouldBeNil)
			So(w.Name, ShouldEqual, fmt.Sprintf("%s_%s", analyzer, platform))
			So(w.Needs, ShouldEqual, f.Needs)
			So(w.Provides, ShouldEqual, f.Provides)
			So(w.ProvidesForPlatform, ShouldEqual, platform)
			So(len(w.Dimensions), ShouldEqual, 1)
			So(w.Dimensions[0], ShouldEqual, dimension)
			So(len(w.CipdPackages), ShouldEqual, 1)
			So(w.Deadline, ShouldEqual, deadline)
			wi := w.Impl.(*admin.Worker_Cmd)
			if wi == nil {
				fail("Incorrect worker type")
			}
			So(len(wi.Cmd.Args), ShouldEqual, 4)
			So(wi.Cmd.Args[0], ShouldEqual, fmt.Sprintf("--%s", config))
			So(wi.Cmd.Args[1], ShouldEqual, configValue)
			So(wi.Cmd.Args[2], ShouldEqual, fmt.Sprintf("--%s", configJSON))
			So(wi.Cmd.Args[3], ShouldEqual, configValueJSON)
		})

		Convey("Correctly creates recipe-based worker", func() {
			f := &tricium.Function{
				Name:       analyzer,
				Needs:      tricium.Data_FILES,
				Provides:   tricium.Data_RESULTS,
				ConfigDefs: []*tricium.ConfigDef{{Name: config}, {Name: configJSON}},
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
								CipdPackage: "path/to/cipd/package",
								CipdVersion: "version",
								Name:        "recipe",
								Properties:  "{\"prop\": \"infra\"}",
							},
						},
						Deadline: deadline,
					},
				},
			}
			w, err := createWorker(selection, sc2, f, gitRef, gitURL)
			So(err, ShouldBeNil)
			So(w.Name, ShouldEqual, fmt.Sprintf("%s_%s", analyzer, platform))
			So(w.Needs, ShouldEqual, f.Needs)
			So(w.Provides, ShouldEqual, f.Provides)
			So(w.ProvidesForPlatform, ShouldEqual, platform)
			So(len(w.Dimensions), ShouldEqual, 1)
			So(w.Dimensions[0], ShouldEqual, dimension)
			So(len(w.CipdPackages), ShouldEqual, 1)
			So(w.Deadline, ShouldEqual, deadline)
			wi := w.Impl.(*admin.Worker_Recipe)
			if wi == nil {
				fail("Incorrect worker type")
			}
			So(wi.Recipe.CipdPackage, ShouldEqual, "path/to/cipd/package")
			So(wi.Recipe.CipdVersion, ShouldEqual, "version")
			So(wi.Recipe.Name, ShouldEqual, "recipe")
			var actualProperties map[string]interface{}
			err = json.Unmarshal([]byte(wi.Recipe.Properties), &actualProperties)
			if err != nil {
				fail("Unable to marshal properties")
			}
			expectedProperties := map[string]interface{}{
				"prop":       "infra",
				"json":       []interface{}{"one", "two"},
				"enable":     "all",
				"ref":        "refs/1234/2",
				"repository": "https://chromium-review.googlesource.com/infra",
			}
			So(actualProperties, ShouldResemble, expectedProperties)
		})

		Convey("Correctly creates recipe-based worker with no properties", func() {
			f := &tricium.Function{
				Name:       analyzer,
				Needs:      tricium.Data_FILES,
				Provides:   tricium.Data_RESULTS,
				ConfigDefs: []*tricium.ConfigDef{{Name: config}, {Name: configJSON}},
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
								CipdPackage: "path/to/cipd/package",
								CipdVersion: "version",
								Name:        "recipe",
							},
						},
						Deadline: deadline,
					},
				},
			}
			w, err := createWorker(selection, sc2, f, gitRef, gitURL)
			So(err, ShouldBeNil)
			So(w.Name, ShouldEqual, fmt.Sprintf("%s_%s", analyzer, platform))
			So(w.Needs, ShouldEqual, f.Needs)
			So(w.Provides, ShouldEqual, f.Provides)
			So(w.ProvidesForPlatform, ShouldEqual, platform)
			So(w.Dimensions, ShouldResemble, []string{dimension})
			So(len(w.CipdPackages), ShouldEqual, 1)
			So(w.Deadline, ShouldEqual, deadline)
			wi := w.Impl.(*admin.Worker_Recipe)
			if wi == nil {
				fail("Incorrect worker type")
			}
			So(wi.Recipe.CipdPackage, ShouldEqual, "path/to/cipd/package")
			So(wi.Recipe.CipdVersion, ShouldEqual, "version")
			So(wi.Recipe.Name, ShouldEqual, "recipe")
			var actualProperties map[string]interface{}
			err = json.Unmarshal([]byte(wi.Recipe.Properties), &actualProperties)
			if err != nil {
				fail("Unable to marshal properties")
			}
			expectedProperties := map[string]interface{}{
				"enable":     "all",
				"json":       []interface{}{"one", "two"},
				"ref":        "refs/1234/2",
				"repository": "https://chromium-review.googlesource.com/infra",
			}
			So(actualProperties, ShouldResemble, expectedProperties)
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
