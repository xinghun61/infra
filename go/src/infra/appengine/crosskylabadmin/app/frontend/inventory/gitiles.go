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

package inventory

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/libs/skylab/inventory"
	"io"

	humanize "github.com/dustin/go-humanize"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/gitiles"
	"golang.org/x/net/context"
)

// fetchLabInventory fetches and parses the inventory data from gitiles.
func fetchLabInventory(ctx context.Context, gc gitiles.GitilesClient) (*inventory.Lab, error) {
	lData, err := fetchLabInventoryData(ctx, gc)
	if err != nil {
		return nil, err
	}
	var lab inventory.Lab
	if err := inventory.LoadLabFromString(lData, &lab); err != nil {
		return nil, err
	}
	return &lab, nil
}

// fetchInfrastructureInventory fetches and parses the inventory data from gitiles.
func fetchInfrastructureInventory(ctx context.Context, gc gitiles.GitilesClient) (*inventory.Infrastructure, error) {
	lData, err := fetchInfraInventoryData(ctx, gc)
	if err != nil {
		return nil, err
	}
	var lab inventory.Infrastructure
	if err := inventory.LoadInfrastructureFromString(lData, &lab); err != nil {
		return nil, err
	}
	return &lab, nil
}

func fetchLabInventoryData(ctx context.Context, gc gitiles.GitilesClient) (string, error) {
	ic := config.Get(ctx).Inventory
	if ic.LabDataPath == "" {
		return "", errors.New("no lab data file path provided in config")
	}

	contents, err := obtainGitilesBytes(ctx, gc, ic)
	if err != nil {
		return "", err
	}

	return extractGitilesArchive(ctx, contents, ic.LabDataPath)
}

func fetchInfraInventoryData(ctx context.Context, gc gitiles.GitilesClient) (string, error) {
	ic := config.Get(ctx).Inventory
	if ic.InfrastructureDataPath == "" {
		return "", errors.New("no infrastructure data file path provided in config")
	}

	contents, err := obtainGitilesBytes(ctx, gc, ic)
	if err != nil {
		return "", err
	}

	return extractGitilesArchive(ctx, contents, ic.InfrastructureDataPath)
}

func obtainGitilesBytes(ctx context.Context, gc gitiles.GitilesClient, ic *config.Inventory) (contents []byte, err error) {
	req := &gitiles.ArchiveRequest{
		Project: ic.Project,
		Ref:     ic.Branch,
		Format:  gitiles.ArchiveRequest_GZIP,
	}
	a, err := gc.Archive(ctx, req)
	if err != nil {
		return nil, errors.Annotate(err, "obtain gitiles archive").Err()
	}
	logging.Debugf(ctx, "Gitiles archive %+v size: %s", req, humanize.Bytes(uint64(len(a.Contents))))

	return a.Contents, nil
}

// extractGitilesArchive extracts file at path filePath from the given
// gunzipped tarfile.
//
// This function takes ownership of data. Caller should not use the byte array
// concurrent to / after this call. See io.Reader interface for more details.
func extractGitilesArchive(ctx context.Context, data []byte, filePath string) (string, error) {
	abuf := bytes.NewBuffer(data)
	gr, err := gzip.NewReader(abuf)
	if err != nil {
		return "", errors.Annotate(err, "gunzip gitiles archive").Err()
	}
	defer gr.Close()

	tr := tar.NewReader(gr)
	for {
		h, err := tr.Next()
		switch {
		case err == io.EOF:
			return "", errors.New("lab inventory data not found in gitiles archive")
		case err != nil:
			return "", errors.Annotate(err, "read gitiles archive tarfile").Err()
		default:
			// good case
		}
		if h.Name != filePath {
			continue
		}

		logging.Debugf(ctx, "Inventory data file %s size %s", h.Name, humanize.Bytes(uint64(h.Size)))
		lData := make([]byte, h.Size)
		if _, err := io.ReadFull(tr, lData); err != nil {
			return string(lData), errors.Annotate(err, "extract inventory archive").Err()
		}
		return string(lData), nil
	}
}
