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
	"io"
	"io/ioutil"
	"net/http"

	"golang.org/x/net/context"
	"golang.org/x/net/context/ctxhttp"

	"go.chromium.org/luci/buildbucket"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/retry/transient"
)

type patchSetAbsenceChecker func(context.Context, *http.Client, buildbucket.BuildSet) (bool, error)

// patchsetAbsent returns true if the patchset referenced by bs does not exist.
// Otherwise false.
func patchSetAbsent(c context.Context, h *http.Client, bs buildbucket.BuildSet) (bool, error) {
	rietveld, ok := bs.(*buildbucket.RietveldChange)
	if !ok {
		return false, nil
	}
	url := fmt.Sprintf("https://%s/api/%d/%d", rietveld.Host, rietveld.Issue, rietveld.PatchSet)
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
