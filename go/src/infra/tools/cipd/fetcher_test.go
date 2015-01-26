// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bytes"
	"io/ioutil"
	"net/url"
	"os"
	"path/filepath"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

func TestFetchInstance(t *testing.T) {
	Convey("Mocking remote service", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tempDir) })
		tempFile := filepath.Join(tempDir, "pkg")

		mockClock(time.Now())
		mockResumableUpload()

		Convey("FetchInstance full flow", func() {
			inst := buildInstanceInMemory("pkgname", nil)
			defer inst.Close()
			service := mockFetchBackend([]PackageInstance{inst})

			out, err := os.OpenFile(tempFile, os.O_WRONLY|os.O_CREATE, 0666)
			So(err, ShouldBeNil)
			closed := false
			defer func() {
				if !closed {
					out.Close()
				}
			}()

			err = FetchInstance(FetchInstanceOptions{
				Client:      service.client,
				Output:      out,
				PackageName: inst.PackageName(),
				InstanceID:  inst.InstanceID(),
			})
			So(err, ShouldBeNil)
			out.Close()
			closed = true

			fetched, err := OpenInstanceFile(tempFile, "")
			So(err, ShouldBeNil)
			So(fetched.PackageName(), ShouldEqual, inst.PackageName())
			So(fetched.InstanceID(), ShouldEqual, inst.InstanceID())
		})
	})
}

func TestFetchAndDeployInstance(t *testing.T) {
	Convey("Mocking temp dir", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tempDir) })

		mockClock(time.Now())
		mockResumableUpload()

		Convey("FetchAndDeployInstance full flow", func() {
			// Build a package instance with some file.
			inst := buildInstanceInMemory("testing/package", []File{
				makeTestFile("file", "test data", false),
			})
			defer inst.Close()
			service := mockFetchBackend([]PackageInstance{inst})

			// Install the package, fetching it from the fake server.
			err = FetchAndDeployInstance(tempDir, FetchInstanceOptions{
				Client:      service.client,
				PackageName: inst.PackageName(),
				InstanceID:  inst.InstanceID(),
			})
			So(err, ShouldBeNil)

			// The file from the package should be installed.
			data, err := ioutil.ReadFile(filepath.Join(tempDir, "file"))
			So(err, ShouldBeNil)
			So(data, ShouldResemble, []byte("test data"))
		})
	})
}

// buildInstanceInMemory makes fully functional PackageInstance object that uses
// memory buffer as a backing store.
func buildInstanceInMemory(pkgName string, files []File) PackageInstance {
	out := bytes.Buffer{}
	err := BuildInstance(BuildInstanceOptions{
		Input:       files,
		Output:      &out,
		PackageName: pkgName,
	})
	So(err, ShouldBeNil)
	inst, err := OpenInstance(bytes.NewReader(out.Bytes()), "")
	So(err, ShouldBeNil)
	return inst
}

// mockFetchBackend returns remoteService that can be used by FetchInstance
// to download the package file (or multiple files).
func mockFetchBackend(instances []PackageInstance) *remoteService {
	var readData = func(i PackageInstance) string {
		r := i.DataReader()
		_, err := r.Seek(0, os.SEEK_SET)
		if err != nil {
			panic(err)
		}
		data, err := ioutil.ReadAll(r)
		if err != nil {
			panic(err)
		}
		return string(data)
	}
	allCalls := []expectedHTTPCall{}
	for _, inst := range instances {
		instCalls := []expectedHTTPCall{
			expectedHTTPCall{
				Method: "GET",
				Path:   "/_ah/api/repo/v1/instance",
				Query: url.Values{
					"instance_id":  []string{inst.InstanceID()},
					"package_name": []string{inst.PackageName()},
				},
				Reply: `{
				"status": "SUCCESS",
				"instance": {
					"registered_by": "user:a@example.com",
					"registered_ts": "0"
				},
				"fetch_url": "http://localhost/fake_fetch_url"
			}`,
			},
			// Simulate a transient error.
			expectedHTTPCall{
				Method: "GET",
				Path:   "/fake_fetch_url",
				Status: 500,
				Reply:  "error",
			},
			expectedHTTPCall{
				Method: "GET",
				Path:   "/fake_fetch_url",
				Status: 200,
				Reply:  readData(inst),
			},
		}
		allCalls = append(allCalls, instCalls...)
	}
	return mockRemoteServiceWithExpectations(allCalls)
}
