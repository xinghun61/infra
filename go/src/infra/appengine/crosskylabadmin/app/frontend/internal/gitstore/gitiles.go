// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package gitstore

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"fmt"
	"io"

	humanize "github.com/dustin/go-humanize"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/gitiles"
	"golang.org/x/net/context"
)

// FilesSpec includes required gitiles information to fetch files.
type FilesSpec struct {
	Project string
	Branch  string
	Paths   []string
}

// FetchFiles download files from gitiles.
func FetchFiles(ctx context.Context, gc gitiles.GitilesClient, fs FilesSpec) (map[string]string, error) {
	sha1, err := fetchLatestSHA1(ctx, gc, fs.Project, fs.Branch)
	if err != nil {
		return nil, errors.Annotate(err, "fail to fetch latest SHA1").Err()
	}
	files, err := fetchFilesFromGitiles(ctx, gc, fs.Project, sha1, fs.Paths)
	if err != nil {
		return nil, errors.Annotate(err, "fail to fetch device config file").Err()
	}
	return files, nil
}

// fetchLatestSHA1 fetches the SHA1 for the latest commit on a branch.
func fetchLatestSHA1(ctx context.Context, gc gitiles.GitilesClient, project string, branch string) (string, error) {
	resp, err := gc.Log(ctx, &gitiles.LogRequest{
		Project:    project,
		Committish: fmt.Sprintf("refs/heads/%s", branch),
		PageSize:   1,
	})
	if err != nil {
		return "", errors.Annotate(err, "fetch sha1 for %s branch of %s", branch, project).Err()
	}
	if len(resp.Log) == 0 {
		return "", fmt.Errorf("fetch sha1 for %s branch of %s: empty git-log", branch, project)
	}
	return resp.Log[0].GetId(), nil
}

// fetchFilesFromGitiles fetches file contents from gitiles.
//
// project is the git project to fetch from.
// ref is the git-ref to fetch from.
// paths lists the paths inside the git project to fetch contents for.
//
// fetchFilesFromGitiles returns a map from path in the git project to the
// contents of the file at that path for each requested path.
func fetchFilesFromGitiles(ctx context.Context, gc gitiles.GitilesClient, project string, ref string, paths []string) (map[string]string, error) {
	contents, err := obtainGitilesBytes(ctx, gc, project, ref)
	if err != nil {
		return make(map[string]string), err
	}
	return extractGitilesArchive(ctx, contents, paths)
}

func obtainGitilesBytes(ctx context.Context, gc gitiles.GitilesClient, project string, ref string) (contents []byte, err error) {
	req := &gitiles.ArchiveRequest{
		Project: project,
		Ref:     ref,
		Format:  gitiles.ArchiveRequest_GZIP,
	}
	a, err := gc.Archive(ctx, req)
	if err != nil {
		return nil, errors.Annotate(err, "obtain gitiles archive").Err()
	}
	logging.Debugf(ctx, "Gitiles archive %+v size: %s", req, humanize.Bytes(uint64(len(a.Contents))))

	return a.Contents, nil
}

// extractGitilesArchive extracts file at each path in paths from the given
// gunzipped tarfile.
//
// extractGitilesArchive returns a map from path to the content of the file at
// that path in the archives for each requested path found in the archive.
//
// This function takes ownership of data. Caller should not use the byte array
// concurrent to / after this call. See io.Reader interface for more details.
func extractGitilesArchive(ctx context.Context, data []byte, paths []string) (map[string]string, error) {
	res := make(map[string]string)
	pmap := make(map[string]bool)
	for _, p := range paths {
		pmap[p] = true
	}

	abuf := bytes.NewBuffer(data)
	gr, err := gzip.NewReader(abuf)
	if err != nil {
		return res, errors.Annotate(err, "extract gitiles archive").Err()
	}
	defer gr.Close()

	tr := tar.NewReader(gr)
	for {
		h, err := tr.Next()
		switch {
		case err == io.EOF:
			// Scanned all files.
			return res, nil
		case err != nil:
			return res, errors.Annotate(err, "extract gitiles archive").Err()
		default:
			// good case.
		}
		if found := pmap[h.Name]; !found {
			continue
		}

		logging.Debugf(ctx, "file: %s, size: %s", h.Name, humanize.Bytes(uint64(h.Size)))
		data := make([]byte, h.Size)
		if _, err := io.ReadFull(tr, data); err != nil {
			return res, errors.Annotate(err, "extract gitiles archive").Err()
		}
		res[h.Name] = string(data)
	}
}
