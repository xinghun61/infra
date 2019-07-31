// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package manifest

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"gopkg.in/yaml.v2"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestManifest(t *testing.T) {
	t.Parallel()

	Convey("Minimal", t, func() {
		m, err := Parse(strings.NewReader(`name: zzz`), "some/dir")
		So(err, ShouldBeNil)
		So(m, ShouldResemble, &Manifest{Name: "zzz"})
	})

	Convey("No name", t, func() {
		_, err := Parse(strings.NewReader(``), "some/dir")
		So(err, ShouldErrLike, `bad "name" field: can't be empty, it's required`)
	})

	Convey("Bad name", t, func() {
		_, err := Parse(strings.NewReader(`name: cheat:tag`), "some/dir")
		So(err, ShouldErrLike, `bad "name" field: "cheat:tag" contains forbidden symbols (any of "/\\:@")`)
	})

	Convey("Not yaml", t, func() {
		_, err := Parse(strings.NewReader(`im not a YAML`), "")
		So(err, ShouldErrLike, "unmarshal errors")
	})

	Convey("Resolving contextdir", t, func() {
		m, err := Parse(
			strings.NewReader("name: zzz\ncontextdir: ../../../blarg/"),
			filepath.FromSlash("root/1/2/3/4"))
		So(err, ShouldBeNil)
		So(m, ShouldResemble, &Manifest{
			Name:       "zzz",
			ContextDir: filepath.FromSlash("root/1/blarg"),
		})
	})

	Convey("Deriving contextdir from dockerfile", t, func() {
		m, err := Parse(
			strings.NewReader("name: zzz\ndockerfile: ../../../blarg/Dockerfile"),
			filepath.FromSlash("root/1/2/3/4"))
		So(err, ShouldBeNil)
		So(m, ShouldResemble, &Manifest{
			Name:       "zzz",
			Dockerfile: filepath.FromSlash("root/1/blarg/Dockerfile"),
			ContextDir: filepath.FromSlash("root/1/blarg"),
		})
	})

	Convey("Resolving imagepins", t, func() {
		m, err := Parse(
			strings.NewReader("name: zzz\nimagepins: ../../../blarg/pins.yaml"),
			filepath.FromSlash("root/1/2/3/4"))
		So(err, ShouldBeNil)
		So(m, ShouldResemble, &Manifest{
			Name:      "zzz",
			ImagePins: filepath.FromSlash("root/1/blarg/pins.yaml"),
		})
	})

	Convey("Empty build step", t, func() {
		_, err := Parse(strings.NewReader(`{"name": "zzz", "build": [
			{"dest": "zzz"}
		]}`), "")
		So(err, ShouldErrLike, "bad build step #1: unrecognized or empty")
	})

	Convey("Ambiguous build step", t, func() {
		_, err := Parse(strings.NewReader(`{"name": "zzz", "build": [
			{"copy": "zzz", "go_binary": "zzz"}
		]}`), "")
		So(err, ShouldErrLike, "bad build step #1: ambiguous")
	})

	Convey("Defaults in CopyBuildStep", t, func() {
		m, err := Parse(strings.NewReader(`{"name": "zzz", "build": [
			{"copy": "../../../blarg/zzz"}
		]}`), filepath.FromSlash("root/1/2/3/4"))
		So(err, ShouldBeNil)
		So(m.Build, ShouldHaveLength, 1)
		So(m.Build[0].Dest, ShouldEqual, "zzz")
		So(m.Build[0].Concrete(), ShouldResemble, &CopyBuildStep{
			Copy: filepath.FromSlash("root/1/blarg/zzz"),
		})
	})

	Convey("Defaults in GoBuildStep", t, func() {
		m, err := Parse(strings.NewReader(`{"name": "zzz", "build": [
			{"go_binary": "go.pkg/some/tool"}
		]}`), filepath.FromSlash("root/1/2/3/4"))
		So(err, ShouldBeNil)
		So(err, ShouldBeNil)
		So(m.Build, ShouldHaveLength, 1)
		So(m.Build[0].Dest, ShouldEqual, "tool")
		So(m.Build[0].Concrete(), ShouldResemble, &GoBuildStep{
			GoBinary: "go.pkg/some/tool",
		})
	})

	Convey("Good infra", t, func() {
		m, err := Parse(strings.NewReader(`{"name": "zzz", "infra": {
			"infra1": {"storage": "gs://bucket"},
			"infra2": {"storage": "gs://bucket/path"}
		}}`), "")
		So(err, ShouldBeNil)
		So(m.Infra, ShouldResemble, map[string]Infra{
			"infra1": {Storage: "gs://bucket"},
			"infra2": {Storage: "gs://bucket/path"},
		})
	})

	Convey("Unsupported storage", t, func() {
		_, err := Parse(strings.NewReader(`{"name": "zzz", "infra": {
			"infra1": {"storage": "ftp://bucket"}
		}}`), "")
		So(err, ShouldErrLike, `in infra section "infra1": bad storage "ftp://bucket", only gs:// is supported currently`)
	})

	Convey("No bucket in storage", t, func() {
		_, err := Parse(strings.NewReader(`{"name": "zzz", "infra": {
			"infra1": {"storage": "gs:///zzz"}
		}}`), "")
		So(err, ShouldErrLike, `in infra section "infra1": bad storage "gs:///zzz", bucket name is missing`)
	})
}

func TestExtends(t *testing.T) {
	t.Parallel()

	Convey("With temp dir", t, func() {
		dir, err := ioutil.TempDir("", "cloudbuildhelper")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(dir) })

		write := func(path string, m Manifest) {
			blob, err := yaml.Marshal(&m)
			So(err, ShouldBeNil)
			p := filepath.Join(dir, filepath.FromSlash(path))
			So(os.MkdirAll(filepath.Dir(p), 0777), ShouldBeNil)
			So(ioutil.WriteFile(p, blob, 0666), ShouldBeNil)
		}

		abs := func(path string) string {
			p, err := filepath.Abs(filepath.Join(dir, filepath.FromSlash(path)))
			So(err, ShouldBeNil)
			return p
		}

		Convey("Works", func() {
			var falseVal = false

			write("base.yaml", Manifest{
				Name:      "base",
				ImagePins: "pins.yaml",
				Infra: map[string]Infra{
					"base": {
						Storage:  "gs://base-storage",
						Registry: "base-registry",
					},
				},
				Build: []*BuildStep{
					{CopyBuildStep: CopyBuildStep{Copy: "base.copy"}},
				},
			})

			write("deeper/mid.yaml", Manifest{
				Name:          "mid",
				Extends:       "../base.yaml",
				Deterministic: &falseVal,
				Infra: map[string]Infra{
					"mid": {
						Storage:  "gs://mid-storage",
						Registry: "mid-registry",
						CloudBuild: CloudBuildConfig{
							Project: "mid-project",
							Docker:  "mid-docker",
						},
					},
				},
				Build: []*BuildStep{
					{CopyBuildStep: CopyBuildStep{Copy: "mid.copy"}},
				},
			})

			write("deeper/leaf.yaml", Manifest{
				Name:       "leaf",
				Extends:    "mid.yaml",
				Dockerfile: "dockerfile",
				ContextDir: "context-dir",
				Infra: map[string]Infra{
					"mid": { // partial override
						Registry: "leaf-registry",
						CloudBuild: CloudBuildConfig{
							Docker: "leaf-docker",
						},
					},
				},
				Build: []*BuildStep{
					{CopyBuildStep: CopyBuildStep{Copy: "leaf.copy"}},
				},
			})

			m, err := Load(filepath.Join(dir, "deeper", "leaf.yaml"))
			So(err, ShouldBeNil)

			// We'll deal with them separately below.
			steps := m.Build
			m.Build = nil

			So(m, ShouldResemble, &Manifest{
				Name:          "leaf",
				Dockerfile:    abs("deeper/dockerfile"),
				ContextDir:    abs("deeper/context-dir"),
				ImagePins:     abs("pins.yaml"),
				Deterministic: &falseVal,
				Infra: map[string]Infra{
					"base": {
						Storage:  "gs://base-storage",
						Registry: "base-registry",
					},
					"mid": {
						Storage:  "gs://mid-storage",
						Registry: "leaf-registry",
						CloudBuild: CloudBuildConfig{
							Project: "mid-project",
							Docker:  "leaf-docker",
						},
					},
				},
			})

			var copySrc []string
			for _, s := range steps {
				copySrc = append(copySrc, s.Copy)
			}
			So(copySrc, ShouldResemble, []string{
				abs("base.copy"),
				abs("deeper/mid.copy"),
				abs("deeper/leaf.copy"),
			})
		})

		Convey("Recursion", func() {
			write("a.yaml", Manifest{Name: "a", Extends: "b.yaml"})
			write("b.yaml", Manifest{Name: "b", Extends: "a.yaml"})

			_, err := Load(filepath.Join(dir, "a.yaml"))
			So(err, ShouldErrLike, "too much nesting")
		})

		Convey("Deep error", func() {
			write("a.yaml", Manifest{Name: "a", Extends: "b.yaml"})
			write("b.yaml", Manifest{
				Name: "b",
				Infra: map[string]Infra{
					"base": {Storage: "bad url"},
				},
			})

			_, err := Load(filepath.Join(dir, "a.yaml"))
			So(err, ShouldErrLike, `bad storage`)
		})
	})
}
