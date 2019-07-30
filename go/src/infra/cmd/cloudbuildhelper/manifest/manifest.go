// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package manifest defines structure of YAML files with target definitions.
package manifest

import (
	"fmt"
	"io"
	"io/ioutil"
	"net/url"
	"path"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v2"

	"go.chromium.org/luci/common/errors"
)

// Manifest is a definition of what to build, how and where.
//
// Comments here describe the structure of the manifest file on disk. In the
// loaded form all paths use filepath.Separator as a directory separator.
type Manifest struct {
	// Name is the name of this target, required.
	//
	// When building Docker images it is an image name (without registry or any
	// tags).
	Name string `yaml:"name"`

	// Dockerfile is a unix-style path to the image's Dockerfile, relative to this
	// YAML file.
	//
	// Presence of this field indicates that the manifest describes how to build
	// a docker image. If its missing, docker related subcommands won't work.
	//
	// All images referenced in this Dockerfile are resolved into concrete digests
	// via an external file. See ImagePins field for more information.
	Dockerfile string `yaml:"dockerfile,omitempty"`

	// ContextDir is a unix-style path to the directory to use as a basis for
	// the build. The path is relative to this YAML file.
	//
	// All files there end up available to the remote builder (e.g. a docker
	// daemon will see this directory as a context directory when building
	// the image).
	//
	// All symlinks there are resolved to their targets. Only +w and +x file mode
	// bits are preserved (all files have 0444 mode by default, +w adds additional
	// 0200 bit and +x adds additional 0111 bis). All other file metadata (owners,
	// setuid bits, modification times) are ignored.
	//
	// The default value depends on whether Dockerfile is set. If it is, then
	// ContextDir defaults to the directory with Dockerfile. Otherwise the context
	// directory is assumed to be empty.
	ContextDir string `yaml:"contextdir,omitempty"`

	// ImagePins is a unix-style path to the YAML file with pre-resolved mapping
	// from (docker image, tag) pair to the corresponding docker image digest.
	//
	// The path is relative to the manifest YAML file. It should point to a YAML
	// file with the following structure:
	//
	//    pins:
	//      - image: <img>
	//        tag: <tag>
	//        digest: sha256:<sha256>
	//      - image: <img>
	//        tag: <tag>
	//        digest: sha256:<sha256>
	//      ...
	//
	// See dockerfile.Pins struct for more details.
	//
	// This file will be used to rewrite the input Dockerfile to reference all
	// images (in "FROM ..." lines) only by their digests. This is useful for
	// reproducibility of builds.
	//
	// Only following forms of "FROM ..." statement are allowed:
	//  * FROM <image> [AS <name>] (assumes "latest" tag)
	//  * FROM <image>[:<tag>] [AS <name>] (resolves the given tag)
	//  * FROM <image>[@<digest>] [AS <name>] (passes the definition through)
	//
	// In particular ARGs in FROM line (e.g. "FROM base:${CODE_VERSION}") are
	// not supported.
	//
	// If not set, the Dockerfile must use only digests to begin with, i.e.
	// all FROM statements should have form "FROM <image>@<digest>".
	//
	// Ignored if Dockerfile field is not set.
	ImagePins string `yaml:"imagepins,omitempty"`

	// Deterministic is true if Dockerfile (with all "FROM" lines resolved) can be
	// understood as a pure function of inputs in ContextDir, i.e. it does not
	// depend on the state of the world.
	//
	// Examples of things that make Dockerfile NOT deterministic:
	//   * Using "apt-get" or any other remote calls to non-pinned resources.
	//   * Cloning repositories from "master" ref (or similar).
	//   * Fetching external resources using curl or wget.
	//
	// When building an image marked as deterministic, the builder will calculate
	// a hash of all inputs (including resolve Dockerfile itself) and check
	// whether there's already an image built from them. If there is, the build
	// will be skipped completely and the existing image reused.
	//
	// Images marked as non-deterministic are always rebuilt and reuploaded, even
	// if nothing in ContextDir has changed.
	Deterministic bool `yaml:"deterministic,omitempty"`

	// Infra is configuration of the build infrastructure to use: Google Storage
	// bucket, Cloud Build project, etc.
	//
	// Keys are names of presets (like "dev", "prod"). What preset is used is
	// controlled via "-infra" command line flag (defaults to "dev").
	Infra map[string]Infra `yaml:"infra"`

	// Build defines a series of local build steps.
	//
	// Each step may add more files to the context directory. The actual
	// `contextdir` directory on disk won't be modified. Files produced here are
	// stored in a temp directory and the final context directory is constructed
	// from the full recursive copy of `contextdir` and files emitted here.
	Build []*BuildStep `yaml:"build,omitempty"`
}

// Infra contains configuration of build infrastructure to use: Google Storage
// bucket, Cloud Build project, etc.
type Infra struct {
	// Storage specifies Google Storage location to store *.tar.gz tarballs
	// produced after executing all local build steps.
	//
	// Expected format is "gs://<bucket>/<prefix>". Tarballs will be stored as
	// "gs://<bucket>/<prefix>/<name>/<sha256>.tar.gz", where <name> comes from
	// the manifest and <sha256> is a hex sha256 digest of the tarball.
	//
	// The bucket should exist already. Its contents is trusted, i.e. if there's
	// an object with desired <sha256>.tar.gz there already, it won't be replaced.
	//
	// Required when using Cloud Build.
	Storage string `yaml:"storage"`

	// Registry is a Cloud Registry to push images to e.g. "gcr.io/something".
	//
	// If empty, images will be built and then just discarded (will not be pushed
	// anywhere). Useful to verify Dockerfile is working without accumulating
	// cruft.
	Registry string `yaml:"registry"`

	// CloudBuild contains configuration of Cloud Build infrastructure.
	CloudBuild CloudBuildConfig `yaml:"cloudbuild"`
}

// CloudBuildConfig contains configuration of Cloud Build infrastructure.
type CloudBuildConfig struct {
	Project string `yaml:"project"` // name of Cloud Project to use for builds
	Docker  string `yaml:"docker"`  // version of "docker" tool to use for builds
}

// BuildStep is one local build operation.
//
// It takes a local checkout and produces one or more output files put into
// the context directory.
//
// This struct is a "case class" with union of all supported build step kinds.
// The chosen "case" is returned by Concrete() method.
type BuildStep struct {
	// Fields common to all build kinds.

	// Dest specifies a location within the context dir to put the result into.
	//
	// Optional in the original YAML, always populated after Manifest is parsed.
	// See individual *BuildStep structs for defaults.
	Dest string `yaml:"dest,omitempty"`

	// Disjoint set of possible build kinds.
	//
	// To add a new step kind:
	//   1. Add a new embedded struct here with definition of the step.
	//   2. Add String() and initStep(...) methods to implement ConcreteBuildStep.
	//   3. Add one more 'if' to initAndSetDefaults(...) below.
	//   4. Add the actual step implementation to builder/step*.go.
	//   5. Add one more type switch to Builder.Build() in builder/builder.go.

	CopyBuildStep `yaml:",inline"` // copy a file or directory into the output
	GoBuildStep   `yaml:",inline"` // build go binary using "go build"

	concrete ConcreteBuildStep // pointer to one of *BuildStep above
}

// ConcreteBuildStep is implemented by various *BuildStep structs.
type ConcreteBuildStep interface {
	String() string // used for human logs only, doesn't have to encode all details

	initStep(bs *BuildStep, cwd string) // populates 'bs' and self
}

// Concrete returns a pointer to some concrete populated *BuildStep.
func (bs *BuildStep) Concrete() ConcreteBuildStep { return bs.concrete }

// CopyBuildStep indicates we want to copy a file or directory.
type CopyBuildStep struct {
	// Copy is a path (relative to the manifest file) to copy files from.
	//
	// Can either be a directory or a file. Whatever it is, it will be put into
	// the output as Dest. By default Dest is a basename of Copy (i.e. we copy
	// Copy into the root of the context dir).
	Copy string `yaml:"copy,omitempty"`
}

func (s *CopyBuildStep) String() string { return fmt.Sprintf("copy %q", s.Copy) }

func (s *CopyBuildStep) initStep(bs *BuildStep, cwd string) {
	normPath(&s.Copy, cwd)
	if bs.Dest == "" {
		bs.Dest = filepath.Base(s.Copy)
	}
}

// GoBuildStep indicates we want to build a go command binary.
type GoBuildStep struct {
	// GoBinary specifies a go command binary to build.
	//
	// This is a path (relative to GOPATH) to some 'main' package. It will be
	// built roughly as:
	//
	//  $ CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build <go_binary> -o <dest>
	//
	// Where <dest> (taken from Dest) is relative to the context directory and set
	// to the go package name by default.
	GoBinary string `yaml:"go_binary,omitempty"`
}

func (s *GoBuildStep) String() string { return fmt.Sprintf("go build %q", s.GoBinary) }

func (s *GoBuildStep) initStep(bs *BuildStep, cwd string) {
	if bs.Dest == "" {
		bs.Dest = path.Base(s.GoBinary)
	}
}

// Read reads and initializes the manifest by filling in all defaults.
//
// If cwd is not empty, rebases all relative paths in it on top of it.
func Read(r io.Reader, cwd string) (*Manifest, error) {
	body, err := ioutil.ReadAll(r)
	if err != nil {
		return nil, errors.Annotate(err, "failed to read the manifest body").Err()
	}
	out := Manifest{}
	if err = yaml.Unmarshal(body, &out); err != nil {
		return nil, errors.Annotate(err, "failed to parse the manifest").Err()
	}
	if err := out.Initialize(cwd); err != nil {
		return nil, err
	}
	return &out, nil
}

// Initialize fills in the defaults.
//
// If cwd is not empty, rebases all relative paths in it on top of it.
//
// Must be called if Manifest{} was allocated in the code (e.g. in unit tests)
// rather than was read via Read(...).
func (m *Manifest) Initialize(cwd string) error {
	if err := validateName(m.Name); err != nil {
		return errors.Annotate(err, `bad "name" field`).Err()
	}
	normPath(&m.Dockerfile, cwd)
	normPath(&m.ContextDir, cwd)
	normPath(&m.ImagePins, cwd)
	if m.ContextDir == "" && m.Dockerfile != "" {
		m.ContextDir = filepath.Dir(m.Dockerfile)
	}
	for k, v := range m.Infra {
		if err := validateInfra(v); err != nil {
			return errors.Annotate(err, "in infra section %q", k).Err()
		}
	}
	for i := range m.Build {
		if err := initAndSetDefaults(m.Build[i], cwd); err != nil {
			return errors.Annotate(err, "bad build step #%d", i+1).Err()
		}
	}
	return nil
}

// validateName validates "name" field in the manifest.
func validateName(t string) error {
	const forbidden = "/\\:@"
	switch {
	case t == "":
		return errors.Reason("can't be empty, it's required").Err()
	case strings.ContainsAny(t, forbidden):
		return errors.Reason("%q contains forbidden symbols (any of %q)", t, forbidden).Err()
	default:
		return nil
	}
}

func validateInfra(i Infra) error {
	if i.Storage != "" {
		url, err := url.Parse(i.Storage)
		if err != nil {
			return errors.Annotate(err, "bad storage %q", i.Storage).Err()
		}
		switch {
		case url.Scheme != "gs":
			return errors.Reason("bad storage %q, only gs:// is supported currently", i.Storage).Err()
		case url.Host == "":
			return errors.Reason("bad storage %q, bucket name is missing", i.Storage).Err()
		}
	}
	return nil
}

func initAndSetDefaults(bs *BuildStep, cwd string) error {
	set := make([]ConcreteBuildStep, 0, 1)
	if bs.CopyBuildStep != (CopyBuildStep{}) {
		set = append(set, &bs.CopyBuildStep)
	}
	if bs.GoBuildStep != (GoBuildStep{}) {
		set = append(set, &bs.GoBuildStep)
	}

	// One and only one substruct should be populated.
	switch {
	case len(set) == 0:
		return errors.Reason("unrecognized or empty").Err()
	case len(set) > 1:
		return errors.Reason("ambiguous").Err()
	default:
		bs.concrete = set[0]
		bs.concrete.initStep(bs, cwd)
		return nil
	}
}

func normPath(p *string, cwd string) {
	if *p != "" {
		*p = filepath.FromSlash(*p)
		if cwd != "" {
			*p = filepath.Join(cwd, *p)
		}
	}
}
