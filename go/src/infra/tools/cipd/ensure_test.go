// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bytes"
	"io/ioutil"
	"net/http"
	"os"
	"path/filepath"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

func TestParseDesiredState(t *testing.T) {
	call := func(data string) ([]PackageState, error) {
		return ParseDesiredState(bytes.NewBufferString(data))
	}

	Convey("ParseDesiredState works", t, func() {
		out, err := call(`
			# Comment

			pkg/a  0000000000000000000000000000000000000000
			pkg/b  1000000000000000000000000000000000000000
		`)
		So(err, ShouldBeNil)
		So(out, ShouldResemble, []PackageState{
			PackageState{
				PackageName: "pkg/a",
				InstanceID:  "0000000000000000000000000000000000000000",
			},
			PackageState{
				PackageName: "pkg/b",
				InstanceID:  "1000000000000000000000000000000000000000",
			},
		})
	})

	Convey("ParseDesiredState empty", t, func() {
		out, err := call("")
		So(err, ShouldBeNil)
		So(out, ShouldResemble, []PackageState{})
	})

	Convey("ParseDesiredState bad package name", t, func() {
		_, err := call("bad.package.name/a  0000000000000000000000000000000000000000")
		So(err, ShouldNotBeNil)
	})

	Convey("ParseDesiredState bad instance ID", t, func() {
		_, err := call("pkg/a  0000")
		So(err, ShouldNotBeNil)
	})

	Convey("ParseDesiredState bad line", t, func() {
		_, err := call("pkg/a)")
		So(err, ShouldNotBeNil)
	})
}

func TestEnsurePackages(t *testing.T) {
	Convey("Mocking temp dir", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tempDir) })

		assertFile := func(relPath, data string) {
			body, err := ioutil.ReadFile(filepath.Join(tempDir, relPath))
			So(err, ShouldBeNil)
			So(string(body), ShouldEqual, data)
		}

		mockClock(time.Now())
		mockResumableUpload()

		Convey("EnsurePackages full flow", func() {
			// Prepare a bunch of packages.
			a1 := buildInstanceInMemory("pkg/a", []File{makeTestFile("file a 1", "test data", false)})
			defer a1.Close()
			a2 := buildInstanceInMemory("pkg/a", []File{makeTestFile("file a 2", "test data", false)})
			defer a2.Close()
			b := buildInstanceInMemory("pkg/b", []File{makeTestFile("file b", "test data", false)})
			defer b.Close()

			// Calls EnsurePackages mocking fetch backend first.
			callEnsure := func(instances []PackageInstance) error {
				states := []PackageState{}
				for _, i := range instances {
					states = append(states, PackageState{
						PackageName: i.PackageName(),
						InstanceID:  i.InstanceID(),
					})
				}
				service := mockFetchBackend(instances)
				return EnsurePackages(EnsurePackagesOptions{
					ClientFactory: func() (*http.Client, error) { return service.client, nil },
					Root:          tempDir,
					Packages:      states,
				})
			}

			// Noop run on top of empty directory.
			err := callEnsure(nil)
			So(err, ShouldBeNil)

			// Specify same package twice.
			err = callEnsure([]PackageInstance{a1, a2})
			So(err, ShouldNotBeNil)

			// Install a1 into a site root.
			err = callEnsure([]PackageInstance{a1})
			So(err, ShouldBeNil)
			assertFile("file a 1", "test data")
			deployed, err := FindDeployed(tempDir)
			So(err, ShouldBeNil)
			So(deployed, ShouldResemble, []PackageState{
				PackageState{
					PackageName: a1.PackageName(),
					InstanceID:  a1.InstanceID(),
				},
			})

			// Noop run.
			err = callEnsure([]PackageInstance{a1})
			So(err, ShouldBeNil)
			assertFile("file a 1", "test data")
			deployed, err = FindDeployed(tempDir)
			So(err, ShouldBeNil)
			So(deployed, ShouldResemble, []PackageState{
				PackageState{
					PackageName: a1.PackageName(),
					InstanceID:  a1.InstanceID(),
				},
			})

			// Upgrade a1 to a2.
			err = callEnsure([]PackageInstance{a2})
			So(err, ShouldBeNil)
			assertFile("file a 2", "test data")
			deployed, err = FindDeployed(tempDir)
			So(err, ShouldBeNil)
			So(deployed, ShouldResemble, []PackageState{
				PackageState{
					PackageName: a2.PackageName(),
					InstanceID:  a2.InstanceID(),
				},
			})

			// Remove a2 and install b.
			err = callEnsure([]PackageInstance{b})
			So(err, ShouldBeNil)
			assertFile("file b", "test data")
			deployed, err = FindDeployed(tempDir)
			So(err, ShouldBeNil)
			So(deployed, ShouldResemble, []PackageState{
				PackageState{
					PackageName: b.PackageName(),
					InstanceID:  b.InstanceID(),
				},
			})

			// Remove b.
			err = callEnsure(nil)
			So(err, ShouldBeNil)
			deployed, err = FindDeployed(tempDir)
			So(err, ShouldBeNil)
			So(deployed, ShouldResemble, []PackageState{})

			// Install a1 and b.
			err = callEnsure([]PackageInstance{a1, b})
			So(err, ShouldBeNil)
			assertFile("file a 1", "test data")
			assertFile("file b", "test data")
			deployed, err = FindDeployed(tempDir)
			So(err, ShouldBeNil)
			So(deployed, ShouldResemble, []PackageState{
				PackageState{
					PackageName: a1.PackageName(),
					InstanceID:  a1.InstanceID(),
				},
				PackageState{
					PackageName: b.PackageName(),
					InstanceID:  b.InstanceID(),
				},
			})
		})
	})
}
