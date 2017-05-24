// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/flag/stringlistflag"
	"github.com/luci/luci-go/common/flag/stringmapflag"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/common/system/environ"

	"infra/tools/kitchen/proto"
	"infra/tools/kitchen/third_party/recipe_engine"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCook(t *testing.T) {
	t.Parallel()
	Convey("cook", t, func() {
		cook := cmdCook.CommandRun().(*cookRun)

		Convey("updateEnv", func() {
			cook.TempDir = "/tmp"
			cook.PrefixPathENV = stringlistflag.Flag{"/path2", "/path3"}
			cook.PythonPaths = stringlistflag.Flag{"/python2", "/python3"}
			cook.SetEnvAbspath = stringmapflag.Value{"FOO": "/bar", "BAZ": "/qux"}

			env := environ.New([]string{"PATH=/path", "PYTHONPATH=/python"})
			cook.updateEnv(env)
			So(env.Map(), ShouldResemble, map[string]string{
				"PATH":       strings.Join([]string{"/path2", "/path3", "/path"}, string(os.PathListSeparator)),
				"PYTHONPATH": strings.Join([]string{"/python2", "/python3", "/python"}, string(os.PathListSeparator)),

				"BAZ": "/qux",
				"FOO": "/bar",

				"TEMPDIR": "/tmp",
				"TMPDIR":  "/tmp",
				"TEMP":    "/tmp",
				"TMP":     "/tmp",
				"MAC_CHROMIUM_TMPDIR": "/tmp",
			})
		})

		Convey("run", func() {
			// Setup context.
			c := context.Background()
			cfg := gologger.LoggerConfig{
				Format: "[%{level:.0s} %{time:2006-01-02 15:04:05}] %{message}",
				Out:    os.Stderr,
			}
			c = cfg.Use(c)
			logCfg := log.Config{
				Level: log.Info,
			}
			c = logCfg.Set(c)

			// Setup tempdir.
			tdir, err := ioutil.TempDir("", "kitchen-test-")
			So(err, ShouldBeNil)
			defer os.RemoveAll(tdir)

			// Prepare paths
			recipeRepoDir := filepath.Join(tdir, "recipe_repo")
			checkoutPath := filepath.Join(tdir, "checkout")
			logdogFilePath := filepath.Join(tdir, "logdog-debug-file.txt")
			resultFilePath := filepath.Join(tdir, "result.json")
			workdirPath := filepath.Join(tdir, "workdir")
			kitchenTempDir := filepath.Join(tdir, "tmp")
			cacheDirPath := filepath.Join(tdir, "cache-dir")

			// Prepare recipe dir.
			So(setupRecipeRepo(c, recipeRepoDir), ShouldBeNil)

			env := environ.System()
			mode := "swarming"

			run := func(mockRecipeResult *recipe_engine.Result, recipeExitCode int) *kitchen.CookResult {
				// Mock recipes.py result
				mockedRecipeResultPath := filepath.Join(tdir, "expected_result.json")
				m := jsonpb.Marshaler{}
				f, err := os.Create(mockedRecipeResultPath)
				So(err, ShouldBeNil)
				defer f.Close()
				err = m.Marshal(f, mockRecipeResult)
				So(err, ShouldBeNil)

				// Prepare arguments
				recipeInputPath := filepath.Join(tdir, "recipe_input.json")
				propertiesJSON, err := json.Marshal(map[string]interface{}{
					"recipe_mock_cfg": map[string]interface{}{
						"input_path":         recipeInputPath,
						"exitCode":           recipeExitCode,
						"mocked_result_path": mockedRecipeResultPath,
					},
				})
				So(err, ShouldBeNil)
				args := []string{
					"-mode", mode,
					"-repository", "file://" + recipeRepoDir,
					"-recipe", "kitchen_test",
					"-properties", string(propertiesJSON),
					"-checkout-dir", checkoutPath,
					"-workdir", workdirPath,
					"-temp-dir", kitchenTempDir,
					"-cache-dir", cacheDirPath,
					"-logdog-annotation-url", "logdog://logdog.example.com/chromium/prefix/+/annotations",
					"-logdog-debug-out-file", logdogFilePath,
					"-output-result-json", resultFilePath,
					"-recipe-result-byte-limit", "500000",
				}

				// Cook.
				err = cook.Flags.Parse(args)
				So(err, ShouldBeNil)
				result := cook.run(c, nil, env)

				// Log results
				t.Logf("cook result:\n%s\n", proto.MarshalTextString(result))
				logdogFileContents, err := ioutil.ReadFile(logdogFilePath)
				if os.IsNotExist(err) {
					t.Logf("logdog file does not exist")
				} else {
					So(err, ShouldBeNil)
					t.Logf("logdog debug file:\n%s\n", logdogFileContents)
				}

				// Check recipes.py input.
				recipeInputFile, err := ioutil.ReadFile(recipeInputPath)
				So(err, ShouldBeNil)
				type recipeInput struct {
					Args       []string
					Properties map[string]interface{}
				}
				var actualRecipeInput recipeInput
				err = json.Unmarshal(recipeInputFile, &actualRecipeInput)
				So(err, ShouldBeNil)
				expectedInputProperties := map[string]interface{}{
					"bot_id":      "bot",
					"path_config": "generic",
					"$recipe_engine/path": map[string]interface{}{
						"cache_dir": cacheDirPath,
						"temp_dir":  filepath.Join(kitchenTempDir, "rt"),
					},
				}
				if mode == "swarming" {
					expectedInputProperties["swarming_run_id"] = "task"
				}
				So(actualRecipeInput, ShouldResemble, recipeInput{
					Args: []string{
						filepath.Join(checkoutPath, "recipes.py"),
						"--operational-args-path", filepath.Join(kitchenTempDir, "rr", "op_args.json"),
						"run",
						"--properties-file", filepath.Join(kitchenTempDir, "rr", "properties.json"),
						"--workdir", workdirPath,
						"--output-result-json", filepath.Join(kitchenTempDir, "recipe-result.json"),
						"kitchen_test",
					},
					Properties: expectedInputProperties,
				})

				return result
			}

			tests := func() {
				Convey("recipe success", func() {
					recipeResult := &recipe_engine.Result{
						OneofResult: &recipe_engine.Result_JsonResult{
							JsonResult: `{"foo": "bar"}`,
						},
					}
					result := run(recipeResult, 0)
					result.Annotations = nil
					So(result, ShouldResemble, &kitchen.CookResult{
						RecipeExitCode: &kitchen.OptionalInt32{Value: 0},
						RecipeResult:   recipeResult,
						AnnotationUrl:  "logdog://logdog.example.com/chromium/prefix/+/annotations",
					})
				})
				Convey("recipe step failed", func() {
					recipeResult := &recipe_engine.Result{
						OneofResult: &recipe_engine.Result_Failure{
							Failure: &recipe_engine.Failure{
								HumanReason: "step failed",
								FailureType: &recipe_engine.Failure_Failure{
									Failure: &recipe_engine.StepFailure{
										Step: "bot_update",
									},
								},
							},
						},
					}
					result := run(recipeResult, 1)
					result.Annotations = nil
					So(result, ShouldResemble, &kitchen.CookResult{
						RecipeExitCode: &kitchen.OptionalInt32{Value: 1},
						RecipeResult:   recipeResult,
						AnnotationUrl:  "logdog://logdog.example.com/chromium/prefix/+/annotations",
					})
				})
			}
			Convey("swarming mode", func() {
				env.Set("SWARMING_TASK_ID", "task")
				env.Set("SWARMING_BOT_ID", "bot")
				tests()
			})
			Convey("buildbot mode", func() {
				mode = "buildbot"
				env.Set("BUILDBOT_SLAVENAME", "bot")
				tests()
			})
		})
	})
}

func setupRecipeRepo(c context.Context, targetDir string) error {
	if err := copyDir(targetDir, filepath.Join("testdata", "recipe_repo")); err != nil {
		return err
	}
	if err := runGit(c, targetDir, "init"); err != nil {
		return err
	}
	if err := runGit(c, targetDir, "add", "-A"); err != nil {
		return err
	}
	if err := runGit(c, targetDir, "commit", "-m", "inital"); err != nil {
		return err
	}
	return nil
}

func copyDir(dest, src string) error {
	return filepath.Walk(src, func(srcPath string, info os.FileInfo, err error) error {
		if filepath.Base(srcPath) == ".recipe_deps" {
			return filepath.SkipDir
		}
		relPath, err := filepath.Rel(src, srcPath)
		if err != nil {
			return err
		}
		destPath := filepath.Join(dest, relPath)
		if info.IsDir() {
			return os.Mkdir(destPath, 0700)
		}

		data, err := ioutil.ReadFile(srcPath)
		if err != nil {
			return err
		}
		return ioutil.WriteFile(destPath, data, info.Mode())
	})
}
