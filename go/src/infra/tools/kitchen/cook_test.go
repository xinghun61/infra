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

	"go.chromium.org/luci/common/auth/authtest"
	"go.chromium.org/luci/common/auth/localauth"
	"go.chromium.org/luci/common/flag/stringlistflag"
	"go.chromium.org/luci/common/flag/stringmapflag"
	log "go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/common/system/environ"
	"go.chromium.org/luci/lucictx"

	"infra/tools/kitchen/build"
	"infra/tools/kitchen/third_party/recipe_engine"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCook(t *testing.T) {
	t.Parallel()
	Convey("cook", t, func() {
		cook := cmdCook.CommandRun().(*cookRun)
		cook.testRun = true

		Convey("updateEnv", func() {
			cook.TempDir = "/tmp"
			cook.PrefixPathENV = stringlistflag.Flag{"/path2", "/path3"}
			cook.SetEnvAbspath = stringmapflag.Value{"FOO": "/bar", "BAZ": "/qux"}

			env := environ.New([]string{"PATH=/path"})
			cook.updateEnv(env)
			So(env.Map(), ShouldResemble, map[string]string{
				"PATH": strings.Join([]string{"/path2", "/path3", "/path"}, string(os.PathListSeparator)),

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

			// Setup fake auth.
			fakeAuth := localauth.Server{
				TokenGenerators: map[string]localauth.TokenGenerator{
					"recipe_acc": &authtest.FakeTokenGenerator{Email: "recipe@example.com"},
					"system_acc": &authtest.FakeTokenGenerator{Email: "system@example.com"},
				},
				DefaultAccountID: "recipe_acc",
			}
			la, err := fakeAuth.Start(c)
			So(err, ShouldBeNil)
			defer fakeAuth.Stop(c)
			c = lucictx.SetLocalAuth(c, la)

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

			env := environ.System()
			mode := "swarming"

			// Prepare recipe dir.
			So(setupRecipeRepo(c, env, recipeRepoDir), ShouldBeNil)

			run := func(mockRecipeResult *recipe_engine.Result, recipeExitCode int) *build.BuildRunResult {
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
					"$kitchen": map[string]interface{}{
						"git_auth": true,
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
					"-luci-system-account", "system_acc",
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

				// Check parsed kitchen own properties.
				So(cook.kitchenProps, ShouldResemble, &kitchenProperties{
					GitAuth: true,
				})

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

			cleanResult := func(r *build.BuildRunResult) *build.BuildRunResult {
				// Set by "ensureAndRunRecipe", but we start testing at "run".
				r.Recipe = nil
				return r
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
					So(cleanResult(result), ShouldResemble, &build.BuildRunResult{
						RecipeExitCode: &build.OptionalInt32{Value: 0},
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
					So(cleanResult(result), ShouldResemble, &build.BuildRunResult{
						RecipeExitCode: &build.OptionalInt32{Value: 1},
						RecipeResult:   recipeResult,
						AnnotationUrl:  "logdog://logdog.example.com/chromium/prefix/+/annotations",
					})
				})
			}
			Convey("swarming mode", func() {
				env.Remove("BUILDBOT_SLAVENAME")
				env.Set("SWARMING_TASK_ID", "task")
				env.Set("SWARMING_BOT_ID", "bot")
				tests()
			})
			Convey("buildbot mode", func() {
				mode = "buildbot"
				env.Set("BUILDBOT_SLAVENAME", "bot")
				env.Remove("SWARMING_TASK_ID")
				env.Remove("SWARMING_BOT_ID")
				tests()
			})
		})
	})
}

func setupRecipeRepo(c context.Context, env environ.Env, targetDir string) error {
	if err := copyDir(targetDir, filepath.Join("testdata", "recipe_repo")); err != nil {
		return err
	}
	if _, err := runGit(c, env, targetDir, "init"); err != nil {
		return err
	}
	if _, err := runGit(c, env, targetDir, "add", "-A"); err != nil {
		return err
	}
	if _, err := runGit(c, env, targetDir, "commit", "-m", "inital"); err != nil {
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
