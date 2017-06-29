// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"time"

	"golang.org/x/net/context"

	"infra/tools/git/state"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/common/system/filesystem"
	"github.com/luci/luci-go/common/testing/testfs"

	. "github.com/smartystreets/goconvey/convey"
)

const testAgentFailedReturnCode = 128

type testAgentRequest struct {
	// ReturnCode is the return code that the agent should return with on success.
	ReturnCode int

	// ReadStdin, if true, instructs the Agent to read from STDIN and reflect it
	// in its response.
	ReadStdin bool

	// Stdout is the content that will be printed to STDOUT.
	Stdout []byte

	// Stderr is the content that will be printed to STDERR.
	Stderr []byte

	// BlockIndefinitely, if true, instructs the process to block indefinitely.
	BlockIndefinitely bool

	// CreateDirectory instructs the agent to create a new directory during
	// execution.
	CreateDirectory string
	// CreateDirectoryExistsReturnCode is the return code that will be returned
	// if CreateDirectory already exists. Otherwise, ReturnCode will be returned.
	CreateDirectoryExistsReturnCode int
}

type testAgentResponse struct {
	// Args is the set of arguments received by the test agent.
	Args []string

	// Env is the initial sorted environment received by the agent.
	Env []string

	// Incomplete indicates that the Agent's execution was incomplete.
	//
	// When the Agent starts, it will write a response with Incomplete set to
	// true. After it intentionally exits, it will write a second response with
	// Incomplete set to false.
	Incomplete bool

	// Stdin is the contents of STDIN, if ReadStdin was true.
	Stdin []byte
}

type testAgent struct {
	inPath  string
	outPath string

	in  testAgentRequest
	out testAgentResponse
}

func TestGitCommand(t *testing.T) {
	// Special testing bootstrap case.
	const runTestAgentENV = "INFRA_TOOLS_GIT__GIT_TEST__TESTING_AGENT"
	testRunnerArgs := []string{"-test.run", "^TestGitCommand$", "--"}
	if tb := os.Getenv(runTestAgentENV); tb != "" {
		c := baseTestContext()

		if err := os.Unsetenv(runTestAgentENV); err != nil {
			logging.Errorf(c, "Failed to clear %q: %s", runTestAgentENV, err)
			os.Exit(testAgentFailedReturnCode)
		}

		// Invoke our main agent entry point.
		//
		// Note that we cut off the executable and injected "-test.run" arguments.
		ta := makeTestAgent(tb)
		os.Exit(ta.run(c, os.Args[1+len(testRunnerArgs):]))
		return
	}

	// Begin: actual test code.
	t.Parallel()

	executable, err := os.Executable()
	if err != nil {
		t.Fatalf("failed to get self executable: %s", err)
	}

	Convey(`Using a test setup for "Git" command`, t, testfs.MustWithTempDir(t, "git_command", func(tdir string) {
		var in testAgentRequest
		var out testAgentResponse
		gc := GitCommand{
			State: state.State{
				GitPath: executable,
			},
			WorkDir: tdir,

			// Skip arguments added in "runAgent".
			testParseSkipArgs: len(testRunnerArgs),
		}
		var env environ.Env

		ta := makeTestAgent(filepath.Join(tdir, "agent_params.json"))

		writeRequest := func() {
			if err := atomicWriteJSON(&in, ta.inPath); err != nil {
				t.Fatalf("Failed to write agent request JSON: %s", err)
			}
		}

		encodeStateENV := func(st state.State) string {
			return strings.Join([]string{gitWrapperENV, st.ToENV()}, "=")
		}

		prepareAgentENV := func(vars ...string) []string {
			env := environ.New(vars)
			return env.Sorted()
		}

		var args []string
		runAgent := func(c context.Context) (int, error) {
			writeRequest()

			// Clone inputs so we can modify them for the test harness.
			env := env.Clone()
			args := append(append([]string(nil), testRunnerArgs...), args...)
			env.Set(runTestAgentENV, ta.inPath)

			rc, err := gc.Run(c, args, env)
			if err == nil && rc == testAgentFailedReturnCode {
				t.Fatalf("Test agent failed: %d", rc)
			}

			// Read our output JSON. Since we move it on atomic completion, if it is
			// present, it is expected to be valid.
			switch _, err := os.Stat(ta.outPath); {
			case err == nil:
				resp, err := ioutil.ReadFile(ta.outPath)
				if err != nil {
					t.Fatalf("Failed to read agent JSON response: %s", err)
				}
				if err := json.Unmarshal(resp, &out); err != nil {
					t.Fatalf("Failed to unmarshal agent params: %s\n%s", err, resp)
				}

			case os.IsNotExist(err):
				t.Logf("WARNING: No agent output file produced.")

			default:
				t.Fatalf("Failed to stat agent output file: %s", err)
			}

			return rc, err
		}

		c := baseTestContext()

		Convey(`Testing GitCommandDirect`, func() {
			args = []string{"status"}

			Convey(`Can perform a basic execution`, func() {
				var stdin = []byte("o hai there!")

				in.ReturnCode = 123
				in.ReadStdin = true

				env.Set("FOO", "BAR")
				gc.LowSpeedLimit = 1000
				gc.LowSpeedTime = 10 * time.Second
				gc.Stdin = bytes.NewReader(stdin)

				rc, err := runAgent(c)
				So(err, ShouldBeNil)
				So(rc, ShouldEqual, in.ReturnCode)

				So(out, ShouldResemble, testAgentResponse{
					Args: []string{"status"},
					Env: prepareAgentENV(
						"FOO=BAR",
						"GIT_HTTP_LOW_SPEED_LIMIT=1000",
						"GIT_HTTP_LOW_SPEED_TIME=10",
						encodeStateENV(gc.State),
					),
					Stdin: stdin,
				})
			})
		})

		Convey(`Testing GitCommandRetry.`, func() {
			args = []string{"clone", "<repo>"}

			Convey(`Can perform a basic execution`, func() {
				var stdin = []byte("o hai there!")
				var stdout, stderr bytes.Buffer

				in.ReturnCode = 123
				in.ReadStdin = true
				in.Stdout = []byte("foo\nbar\nbaz")
				in.Stderr = []byte("qux\npants\nshirt")

				env.Set("FOO", "BAR")
				gc.LowSpeedLimit = 1000
				gc.LowSpeedTime = 10 * time.Second
				gc.Stdin = bytes.NewReader(stdin)
				gc.Stdout = &stdout
				gc.Stderr = &stderr

				rc, err := runAgent(c)
				So(err, ShouldBeNil)
				So(rc, ShouldEqual, in.ReturnCode)

				st := gc.State
				st.Retrying = true

				So(out, ShouldResemble, testAgentResponse{
					Args: []string{"clone", "<repo>"},
					Env: prepareAgentENV(
						"FOO=BAR",
						"GIT_HTTP_LOW_SPEED_LIMIT=1000",
						"GIT_HTTP_LOW_SPEED_TIME=10",
						encodeStateENV(st),
					),
					Stdin: stdin,
				})
				So(stdout.Bytes(), ShouldResemble, in.Stdout)
				So(stderr.Bytes(), ShouldResemble, in.Stderr)
			})

			Convey(`Will fail if Git target does not exist`, func() {
				gc.State.GitPath = filepath.Join(tdir, "nonexist")

				_, err := runAgent(c)
				So(err, ShouldNotBeNil)
			})

			Convey(`When configured with a retry regexp`, func() {
				const numRetries = 10
				counter := 0
				var onNext func()
				gc.RetryList = []*regexp.Regexp{
					regexp.MustCompile("foo.*bar.*baz"),
				}
				gc.Retry = func() retry.Iterator { return &countingRetryIterator{&counter, numRetries, &onNext} }

				for _, tc := range []struct {
					name      string
					installTo *[]byte
				}{
					{"stdout", &in.Stdout},
					{"stderr", &in.Stderr},
				} {
					Convey(fmt.Sprintf(`When configured to emit that regexp to %s.`, tc.name), func() {
						*tc.installTo = []byte(strings.Join([]string{
							"nothing to see here",
							"splitting: foo bar",
							"baz end split",
							"one line foo bar baz end line",
							"tail",
						}, "\n"))

						Convey(`Will not retry if the process returns zero.`, func() {
							rc, err := runAgent(c)
							So(err, ShouldBeNil)
							So(rc, ShouldEqual, in.ReturnCode)
							So(counter, ShouldEqual, 0)
						})

						Convey(`Will not retry if already retrying.`, func() {
							gc.State.Retrying = true
							in.ReturnCode = 42

							rc, err := runAgent(c)
							So(err, ShouldBeNil)
							So(rc, ShouldEqual, in.ReturnCode)
							So(counter, ShouldEqual, 0)
						})

						Convey(`Will retry if the process returns non-zero.`, func() {
							in.ReturnCode = 42

							rc, err := runAgent(c)
							So(err, ShouldBeNil)
							So(rc, ShouldEqual, in.ReturnCode)
							So(counter, ShouldEqual, numRetries+1)
						})

						Convey(`Will stop retrying if a subsequent attempt returns zero.`, func() {
							in.ReturnCode = 42
							onNext = func() {
								if counter == numRetries-1 {
									// The next time we run, we will return 0.
									in.ReturnCode = 0
									writeRequest()
								}
							}

							rc, err := runAgent(c)
							So(err, ShouldBeNil)
							So(rc, ShouldEqual, 0)
							So(counter, ShouldEqual, numRetries-1)
						})

						Convey(`Will stop retrying if a subsequent does not include a retry string.`, func() {
							in.ReturnCode = 42
							onNext = func() {
								if counter == numRetries-1 {
									// The next time we run, we will not output a transient error
									// string.
									*tc.installTo = []byte("does not match the regex")
									writeRequest()
								}
							}

							rc, err := runAgent(c)
							So(err, ShouldBeNil)
							So(rc, ShouldEqual, in.ReturnCode)
							So(counter, ShouldEqual, numRetries-1)
						})
					})

					Convey(fmt.Sprintf(`Will not retry if that regexp is not encountered (%s).`, tc.name), func() {
						in.ReturnCode = 42
						*tc.installTo = []byte(strings.Join([]string{
							"nothing to see here",
							"splitting: foo bar",
							"baz end split",
							"tail",
						}, "\n"))

						rc, err := runAgent(c)
						So(err, ShouldBeNil)
						So(rc, ShouldEqual, in.ReturnCode)
						So(counter, ShouldEqual, 0)
					})
				}

				Convey(`Will retry if the regexp is encountered on both STDOUT and STDERR.`, func() {
					in.ReturnCode = 42
					in.Stdout = []byte("ohai there foo, how are bar and baz?")
					in.Stderr = []byte("there once was a dog named foo, who passed the bar a bazillion times.")

					rc, err := runAgent(c)
					So(err, ShouldBeNil)
					So(rc, ShouldEqual, in.ReturnCode)
					So(counter, ShouldEqual, 11)
				})
			})

			Convey(`Can be terminated by cancelling the Context.`, func() {
				c, cancelFunc := context.WithCancel(c)
				defer cancelFunc()

				// The process will block indefinitely. After it has successfully started,
				// cancel out Context to terminate it.
				in.BlockIndefinitely = true

				// Poll for our incomplete output file, then cancel.
				gc.testOnStart = func() {
					for {
						t.Logf("Polling for output file [%s]...", ta.outPath)
						switch _, err := os.Stat(ta.outPath); {
						case err == nil:
							cancelFunc()
							return

						case os.IsNotExist(err):
							time.Sleep(10 * time.Millisecond)

						default:
							t.Fatalf("Failed to poll for output file [%q]: %s", ta.outPath, err)
						}
					}
				}

				rc, err := runAgent(c)
				So(err, ShouldBeNil)
				So(rc, ShouldNotEqual, 0)
				So(out.Incomplete, ShouldBeTrue)
			})
		})

		Convey(`Testing GitCommandAugmentVersion`, func() {
			args = []string{"version"}

			var stdout bytes.Buffer
			gc.Stdout = &stdout

			Convey(`If the Agent emits a single line, will augment it with our version.`, func() {
				in.Stdout = []byte("foo\n")

				rc, err := runAgent(c)
				So(err, ShouldBeNil)
				So(rc, ShouldEqual, 0)
				So(out.Args, ShouldResemble, args)

				v := stdout.String()
				So(v, ShouldStartWith, "foo")
				So(v, ShouldContainSubstring, "/ Infra wrapper")
				So(v, ShouldEndWith, "\n")
			})

			Convey(`If the Agent emits no newline, will not augment anything.`, func() {
				in.Stdout = []byte("foo")

				rc, err := runAgent(c)
				So(err, ShouldBeNil)
				So(rc, ShouldEqual, 0)
				So(stdout.Bytes(), ShouldResemble, in.Stdout)
			})
		})

		Convey(`Testing "clone" subcommand directory deletion`, func() {
			dest := filepath.Join(tdir, "destination")
			args = []string{"clone", "https://foo.example.com/something.git", dest}

			// Configure semantics of "clone", which is to create a new directory
			// on execution and fail if the destination directory already exists.
			in.CreateDirectory = dest
			in.CreateDirectoryExistsReturnCode = 2

			// Configure the process to transiently retry indefinitely. By default, if
			// the return code is 0, this won't actually result in any retries. We can
			// trigger this behavior by setting the return code to non-zero.
			const numRetries = 10
			counter := 0
			var onNext func()
			gc.RetryList = []*regexp.Regexp{
				regexp.MustCompile("transient"),
			}
			gc.Retry = func() retry.Iterator { return &countingRetryIterator{&counter, numRetries, &onNext} }
			in.Stdout = []byte("transient")

			Convey(`Can successfully execute the command.`, func() {
				rc, err := runAgent(c)
				So(err, ShouldBeNil)
				So(rc, ShouldEqual, 0)
				So(out.Args, ShouldResemble, args)
				So(counter, ShouldEqual, 0)

				// After all of the retries, the path should exist.
				So(pathExists(dest), ShouldBeTrue)
			})

			Convey(`If the command fails, will recreate and retry, deleting the directory in between.`, func() {
				in.ReturnCode = 1

				Convey(`Relative directory`, func() {
					rc, err := runAgent(c)
					So(err, ShouldBeNil)
					So(rc, ShouldEqual, in.ReturnCode)
					So(out.Args, ShouldResemble, args)
					So(counter, ShouldEqual, numRetries+1)

					// After all of the retries, the path should still exist.
					So(pathExists(dest), ShouldBeTrue)
				})

				Convey(`Honors the "-C" Git flag`, func() {
					// Using "dest", so no need to update agent arguments.
					args = []string{
						"-C", filepath.Dir(dest),
						"clone", "https://foo.example.com/something.git", filepath.Base(dest),
					}

					rc, err := runAgent(c)
					So(err, ShouldBeNil)
					So(rc, ShouldEqual, in.ReturnCode)
					So(out.Args, ShouldResemble, args)
					So(counter, ShouldEqual, numRetries+1)

					// After all of the retries, the path should still exist.
					So(pathExists(dest), ShouldBeTrue)
				})
			})

			Convey(`If the command permanently fails, the diectory will remain.`, func() {
				in.ReturnCode = 1

				onNext = func() {
					if counter == numRetries-1 {
						// The next time we run, we will return 0.
						in.ReturnCode = 2
						in.Stdout = nil
						writeRequest()
					}
				}

				rc, err := runAgent(c)
				So(err, ShouldBeNil)
				So(rc, ShouldEqual, 2)
				So(out.Args, ShouldResemble, args)
				So(counter, ShouldEqual, numRetries-1)

				// After all of the retries, the path should still exist.
				So(pathExists(dest), ShouldBeTrue)
			})

			Convey(`If the directory already existed, we won't delete it on transient failure.`, func() {
				in.ReturnCode = 1
				if err := filesystem.MakeDirs(dest); err != nil {
					t.Fatalf("failed to create directory: %s", err)
				}

				rc, err := runAgent(c)
				So(err, ShouldBeNil)
				So(rc, ShouldEqual, in.CreateDirectoryExistsReturnCode)
				So(out.Args, ShouldResemble, args)
				So(counter, ShouldEqual, numRetries+1)

				// After all of the retries, the path should still exist.
				So(pathExists(dest), ShouldBeTrue)
			})
		})
	}))

	Convey(`Unittests`, t, func() {
		Convey(`For windows`, func() {
			gitPathPrefix := "cool/path/to/git"
			gr := &gitRunner{
				GitCommand: &GitCommand{
					State: state.State{},
				},
				testGOOS: "windows",
			}

			Convey(`We properly escape the '^' symbol when invoking a batfile`, func() {
				gitPath := gitPathPrefix + ".Bat"
				gr.GitCommand.State.GitPath = gitPath
				gr.Args = []string{"diff-tree", "HEAD^!"}
				cmd := gr.setupCommand(context.Background())
				So(cmd.Args, ShouldResemble, []string{gitPath, "diff-tree", "HEAD^^^^!"})
			})

			Convey(`Should leave things alone when invoking an exe`, func() {
				gitPath := gitPathPrefix + ".exe"
				gr.GitCommand.State.GitPath = gitPath
				gr.Args = []string{"diff-tree", "HEAD^!"}
				cmd := gr.setupCommand(context.Background())
				So(cmd.Args, ShouldResemble, []string{gitPath, "diff-tree", "HEAD^!"})
			})
		})
	})
}

func makeTestAgent(inPath string) *testAgent {
	return &testAgent{
		inPath:  inPath,
		outPath: inPath + ".out",
	}
}

func (ta *testAgent) readRequest() error {
	// Read in our request.
	d, err := ioutil.ReadFile(ta.inPath)
	if err != nil {
		return errors.Annotate(err, "failed to read input params").Err()
	}

	if err := json.Unmarshal(d, &ta.in); err != nil {
		return errors.Annotate(err, "failed to unmarshal input params").Err()
	}

	return nil
}

func (ta *testAgent) writeResponse() (err error) {
	if err := atomicWriteJSON(&ta.out, ta.outPath); err != nil {
		return errors.Annotate(err, "failed to write output JSON").Err()
	}

	return nil
}

func (ta *testAgent) run(c context.Context, args []string) int {
	ta.out = testAgentResponse{
		Args:       args,
		Env:        environ.System().Sorted(),
		Incomplete: true,
	}

	// Always emit our output params ("incomplete").
	if err := ta.writeResponse(); err != nil {
		errors.Log(c, err)
		return testAgentFailedReturnCode
	}

	// Read our input request JSON.
	if err := ta.readRequest(); err != nil {
		errors.Log(c, err)
		return testAgentFailedReturnCode
	}

	// Process our request, update our response.
	rc := ta.in.ReturnCode
	if err := ta.processRequest(c, args, &rc); err != nil {
		errors.Log(c, err)
		return testAgentFailedReturnCode
	}

	// Write our final response ("complete") output on completion.
	ta.out.Incomplete = false
	if err := ta.writeResponse(); err != nil {
		errors.Log(c, err)
		return testAgentFailedReturnCode
	}

	return rc
}

// testGitCommandAgent is the TestGitCommand testing agent entry point.
func (ta *testAgent) processRequest(c context.Context, args []string, rc *int) error {
	if ta.in.ReadStdin {
		var err error
		if ta.out.Stdin, err = ioutil.ReadAll(os.Stdin); err != nil {
			return errors.Annotate(err, "failed to read STDIN").Err()
		}
	}

	// Write STDOUT / STDERR.
	if _, err := os.Stdout.Write(ta.in.Stdout); err != nil {
		return errors.Annotate(err, "failed to write STDOUT").Err()
	}
	if _, err := os.Stderr.Write(ta.in.Stderr); err != nil {
		return errors.Annotate(err, "failed to write STDERR").Err()
	}

	if d := ta.in.CreateDirectory; d != "" {
		if pathExists(d) {
			*rc = ta.in.CreateDirectoryExistsReturnCode
			return nil
		}

		if err := filesystem.MakeDirs(d); err != nil {
			return errors.Annotate(err, "failed to create directory").Err()
		}
	}

	if ta.in.BlockIndefinitely {
		for {
			time.Sleep(time.Second)
		}
	}

	return nil
}

type countingRetryIterator struct {
	counter *int
	retries int

	onNext *func()
}

func (it *countingRetryIterator) Next(context.Context, error) time.Duration {
	*it.counter++
	if it.retries == 0 {
		return retry.Stop
	}
	it.retries--

	if fn := *it.onNext; fn != nil {
		fn()
	}

	return 0
}

func atomicWriteJSON(obj interface{}, path string) (err error) {
	fd, err := ioutil.TempFile(filepath.Dir(path), filepath.Base(path))
	if err != nil {
		return errors.Annotate(err, "failed to create output tempfile").Err()
	}

	if err := json.NewEncoder(fd).Encode(obj); err != nil {
		fd.Close()
		return errors.Annotate(err, "failed to encode JSON").Err()
	}

	if err := fd.Close(); err != nil {
		return errors.Annotate(err, "failed to close output file").Err()
	}

	if err := os.Rename(fd.Name(), path); err != nil {
		return errors.Annotate(err, "failed to install output file").Err()
	}

	return nil
}

func pathExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
