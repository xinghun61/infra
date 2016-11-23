package som

import (
	"encoding/base64"
	"fmt"
	"io/ioutil"
	"net/http"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/appengine/gaeauth/client"
	"github.com/luci/luci-go/common/auth"
)

var (
	gitilesScope       = "https://www.googleapis.com/auth/gerritcodereview"
	gitilesCachePrefix = "gitiles:"
)

// TODO(seanmccullough): refactor this into one of our shared packages.
func getGitiles(c context.Context, URL string) ([]byte, error) {
	token, err := client.GetAccessToken(c, []string{gitilesScope})
	if err != nil {
		return nil, err
	}

	trans := auth.NewModifyingTransport(urlfetch.Get(c), func(req *http.Request) error {
		req.Header.Add("Authorization", fmt.Sprintf("Bearer %s", token.AccessToken))
		return nil
	})

	client := &http.Client{Transport: trans}

	resp, err := client.Get(URL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP status code %d from %s", resp.StatusCode, resp.Request.URL)
	}

	// This is currently only used for fetching gitiles files with ?format=text,
	// which will return the body base64 encoded. Response headers don't indicate
	// this encoding (sigh) so we may need to some extra logic here to make this
	// decoding conditional on some other heuristic, like request parameters.
	reader := base64.NewDecoder(base64.StdEncoding, resp.Body)
	b, err := ioutil.ReadAll(reader)
	if err != nil {
		return nil, err
	}
	return b, nil
}
