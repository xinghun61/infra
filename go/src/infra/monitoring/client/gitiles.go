package client

import (
	"encoding/base64"
	"fmt"
	"io/ioutil"
	"net/http"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/appengine/gaeauth/client"
	"go.chromium.org/luci/common/auth"
	"go.chromium.org/luci/common/logging"
)

var (
	gitilesScope       = "https://www.googleapis.com/auth/gerritcodereview"
	gitilesCachePrefix = "gitiles:"
)

// GetGitilesCached fetches gitiles content through memcache. Note that this
// currently only works from AppEngine due to memcache and gaeauth dependencies.
func GetGitilesCached(c context.Context, URL string) ([]byte, error) {
	item, err := memcache.GetKey(c, gitilesCachePrefix+URL)
	if err != nil && err != memcache.ErrCacheMiss {
		return nil, err
	}

	var b []byte
	if err == memcache.ErrCacheMiss {
		b, err = GetGitiles(c, URL)
		if err != nil {
			return nil, err
		}

		item = memcache.NewItem(c, gitilesCachePrefix+URL).SetValue(b).SetExpiration(5 * time.Minute)
		err = memcache.Set(c, item)
	}

	if err != nil {
		return nil, err
	}

	return item.Value(), nil
}

// GetGitiles fetches gitiles raw text content with requried authentication headers.
// Note that this currently only works from AppEngine due to gaeauth dependencies.
func GetGitiles(c context.Context, URL string) ([]byte, error) {
	token, err := client.GetAccessToken(c, []string{gitilesScope})
	if err != nil {
		logging.Errorf(c, "getting access token: %v", err)
		return nil, err
	}

	trans := auth.NewModifyingTransport(urlfetch.Get(c), func(req *http.Request) error {
		req.Header.Add("Authorization", fmt.Sprintf("Bearer %s", token.AccessToken))
		return nil
	})

	client := &http.Client{Transport: trans}

	resp, err := client.Get(URL)
	if err != nil {
		logging.Errorf(c, "getting URL: %v", err)
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP status code %d from %s", resp.StatusCode, resp.Request.URL)
	}

	defer resp.Body.Close()

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
