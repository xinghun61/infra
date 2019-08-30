// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"encoding/json"
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"

	"go.chromium.org/luci/auth/integration/authtest"
	"go.chromium.org/luci/auth/integration/localauth"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	log "go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/common/system/environ"
	"go.chromium.org/luci/lucictx"

	"infra/tools/kitchen/third_party/recipe_engine"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCook(t *testing.T) {
	// TODO(crbug.com/904533): Running tests that use git in parallel may be
	// causing issues on Windows.
	//
	// t.Parallel()

	Convey("cook", t, func() {
		cook := cmdCook.CommandRun().(*cookRun)

		Convey("updateEnv", func() {
			tdir, err := ioutil.TempDir("", "kitchen-test-")
			So(err, ShouldBeNil)
			defer os.RemoveAll(tdir)

			cook.TempDir = tdir
			expected := filepath.Join(tdir, "t")

			env := environ.New(nil)
			So(cook.updateEnv(env), ShouldBeNil)
			So(env.Map(), ShouldResemble, map[string]string{
				"TEMPDIR":             expected,
				"TMPDIR":              expected,
				"TEMP":                expected,
				"TMP":                 expected,
				"MAC_CHROMIUM_TMPDIR": expected,
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
					"recipe_acc": &authtest.FakeTokenGenerator{
						Email: "recipe@example.com",
					},
					"system_acc": &authtest.FakeTokenGenerator{
						Email: "system@example.com",
					},
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

			// OS X has symlinks in its TempDir return values by default.
			tdir, err = filepath.EvalSymlinks(tdir)
			So(err, ShouldBeNil)

			// Prepare paths
			recipeRepoDir := filepath.Join(tdir, "recipe_repo")
			resultFilePath := filepath.Join(tdir, "result.json")
			workdirPath := filepath.Join(tdir, "k")
			kitchenTempDir := filepath.Join(tdir, "tmp")
			cacheDirPath := filepath.Join(tdir, "cache-dir")

			env := environ.System()

			// Prepare recipe dir.
			So(setupRecipeRepo(c, env, recipeRepoDir), ShouldBeNil)

			// Kitchen works relative to its cwd
			cwd, err := os.Getwd()
			So(err, ShouldBeNil)
			So(os.Chdir(tdir), ShouldBeNil)
			defer os.Chdir(cwd)

			run := func(mockRecipeResult *recipe_engine.Result, recipeExitCode int) (*buildbucketpb.Build, int) {
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
						"git_auth":    true,
						"emulate_gce": true,
					},
				})
				So(err, ShouldBeNil)
				args := []string{
					"-recipe", "kitchen_test",
					"-properties", string(propertiesJSON),
					"-checkout-dir", recipeRepoDir,
					"-temp-dir", kitchenTempDir,
					"-cache-dir", cacheDirPath,
					"-logdog-annotation-url", "logdog://logdog.example.com/chromium/prefix/+/annotations",
					"-logdog-null-output",
					"-output-result-json", resultFilePath,
					"-recipe-result-byte-limit", "500000",
					"-luci-system-account", "system_acc",
				}

				// Cook.
				err = cook.Flags.Parse(args)
				So(err, ShouldBeNil)
				result, outputExitCode := cook.run(c, nil, env)

				// Log results
				t.Logf("cook result:\n%s\n", proto.MarshalTextString(result))

				// Check parsed kitchen own properties.
				So(cook.kitchenProps, ShouldResemble, &kitchenProperties{
					GitAuth:      true,
					EmulateGCE:   true,
					DockerAuth:   true,
					FirebaseAuth: false,
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
						filepath.Join(recipeRepoDir, "recipes"),
						"run",
						"--properties-file", filepath.Join(kitchenTempDir, "rr", "properties.json"),
						"--workdir", workdirPath,
						"--output-result-json", filepath.Join(kitchenTempDir, "recipe-result.json"),
						"kitchen_test",
					},
					Properties: expectedInputProperties,
				})

				return result, outputExitCode
			}

			env.Set("SWARMING_TASK_ID", "task")
			env.Set("SWARMING_BOT_ID", "bot")

			Convey("recipe success", func() {
				recipeResult := &recipe_engine.Result{
					OneofResult: &recipe_engine.Result_JsonResult{
						JsonResult: `{"foo": "bar"}`,
					},
				}
				result, exitCode := run(recipeResult, 0)
				So(exitCode, ShouldEqual, 0)
				So(result.Status, ShouldEqual, buildbucketpb.Status_SUCCESS)
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
				result, exitCode := run(recipeResult, 1)
				So(exitCode, ShouldEqual, 1)
				So(result.Status, ShouldEqual, buildbucketpb.Status_FAILURE)
				So(result.SummaryMarkdown, ShouldEqual, recipeResult.GetFailure().HumanReason)
			})
		})
	})
}

func setupRecipeRepo(c context.Context, env environ.Env, targetDir string) error {
	if err := copyDir(targetDir, filepath.Join("testdata", "recipe_repo")); err != nil {
		return err
	}
	return nil
}

func copyDir(dest, src string) error {
	return filepath.Walk(src, func(srcPath string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
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
