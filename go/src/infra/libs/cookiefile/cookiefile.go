// Package cookiefile implements a CookieJar over a standard
// Netscape/curl format cookie file.
//
// https://curl.haxx.se/docs/http-cookies.html
package cookiefile

import (
	"bufio"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"strconv"
	"strings"
	"time"

	"go.chromium.org/luci/common/errors"
	"golang.org/x/net/publicsuffix"
)

// NewJar returns a new cookie jar containing the given cookies.
func NewJar(c []*http.Cookie) (*cookiejar.Jar, error) {
	j, err := cookiejar.New(&cookiejar.Options{
		PublicSuffixList: publicsuffix.List,
	})
	if err != nil {
		return nil, errors.Annotate(err, "failed to create cookiejar").Err()
	}
	for _, c := range c {
		u := url.URL{
			Scheme: "https",
			Host:   c.Domain,
		}
		j.SetCookies(&u, []*http.Cookie{c})
	}
	return j, nil
}

// Read reads the cookie file data and returns its cookies.
func Read(r io.Reader) ([]*http.Cookie, error) {
	var cookies []*http.Cookie
	scanner := bufio.NewScanner(r)
	for scanner.Scan() {
		line := scanner.Text()
		if len(line) == 0 {
			continue
		}
		// BUG(ayatane@chromium.org): Read handles comments
		// only when they start at the beginning of the line.
		// That is probably good enough since the format isn't
		// specified anywhere.
		if line[0] == '#' {
			continue
		}
		parts := strings.Split(line, "\t")
		if len(parts) != 7 {
			return nil, errors.Reason("failed to read cookie file: malformed line %s", line).Err()
		}
		var c http.Cookie
		// See https://unix.stackexchange.com/a/210282 for the format
		c.Domain = parts[0]
		// Ignore parts[1].
		c.Path = parts[2]
		switch parts[3] {
		case "TRUE":
			c.Secure = true
		case "FALSE":
			c.Secure = false
		default:
			return nil, errors.Reason("failed to read cookie file: invalid secure value %s", parts[3]).Err()
		}
		expires, err := strconv.ParseInt(parts[4], 10, 64)
		if err != nil {
			return nil, errors.Annotate(err, "failed to read cookie file: invalid expiration value %s", parts[4]).Err()
		}
		c.Expires = time.Unix(expires, 0)
		c.Name = parts[5]
		c.Value = parts[6]
		cookies = append(cookies, &c)
	}
	if err := scanner.Err(); err != nil {
		return nil, errors.Annotate(err, "failed to read cookie file").Err()
	}
	return cookies, nil

}
