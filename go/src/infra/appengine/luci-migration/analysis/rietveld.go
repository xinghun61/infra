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
