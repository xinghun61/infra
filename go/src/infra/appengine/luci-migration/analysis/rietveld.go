// Copyright 2017 The LUCI Authors.
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

package analysis

import (
	"fmt"
	"net/http"

	"golang.org/x/net/context"
	"golang.org/x/net/context/ctxhttp"

	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/retry/transient"

	"infra/appengine/luci-migration/bbutil/buildset"
	"io"
	"io/ioutil"
)

type patchSetAbsenceChecker func(context.Context, *http.Client, *buildset.BuildSet) (bool, error)

// patchsetAbsent returns true if the patchset referenced by bs does not exist.
// Otherwise false.
func patchSetAbsent(c context.Context, h *http.Client, bs *buildset.BuildSet) (bool, error) {
	if bs == nil || bs.Rietveld == nil {
		return false, nil
	}
	url := fmt.Sprintf("https://%s/api/%d/%d", bs.Rietveld.Hostname, bs.Rietveld.Issue, bs.Rietveld.Patchset)
	return is404(c, h, url)
}

func is404(c context.Context, h *http.Client, url string) (is404 bool, err error) {
	err = retry.Retry(c, retry.Default, func() error {
		res, err := ctxhttp.Get(c, h, url)
		if err != nil {
			return transient.Tag.Apply(err)
		}
		io.Copy(ioutil.Discard, res.Body) // ensure connection can be reused
		res.Body.Close()
		switch {
		case res.StatusCode == http.StatusNotFound:
			is404 = true
			return nil
		case res.StatusCode == http.StatusOK:
			return nil
		case res.StatusCode < 500:
			return fmt.Errorf("HTTP %d", res.StatusCode)
		default:
			return transient.Tag.Apply(fmt.Errorf("HTTP %d", res.StatusCode))
		}
	}, nil)
	return
}
