package frontend

import (
	"archive/zip"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"

	"infra/appengine/test-results/model"

	"golang.org/x/net/context"

	"cloud.google.com/go/storage"
	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/common/gcloud/gs"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
)

var builderNameReplacedStrings = []string{".", "(", ")", " "}

// getZipHandler handles a request to get a file from a zip archive.
// This saves content etags in memcache, to save round trip time on fetching
// zip files over the network, so that clients can cache the data.
func getZipHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	builder := p.ByName("builder")
	for _, s := range builderNameReplacedStrings {
		builder = strings.Replace(builder, s, "_", -1)
	}
	// buildNum may sometimes not be a number, if the user asks for <builder>/results
	// which is the latest results for the builder.  ¯\_(ツ)_/¯
	buildNum := p.ByName("buildnum")
	filepath := strings.Trim(p.ByName("filepath"), "/")

	// Special case, since this isn't the zip file.
	if strings.HasSuffix(filepath, "layout-test-results.zip") {
		newURL := fmt.Sprintf("https://storage.googleapis.com/chromium-layout-test-archives/%s/%s/%s", builder, buildNum, filepath)
		http.Redirect(w, r, newURL, http.StatusPermanentRedirect)
		return
	}
	mkey := fmt.Sprintf("gs_etag%s/%s/%s", builder, buildNum, filepath)

	// This content should never change; safe to cache for 1 day.
	w.Header().Set("Cache-Control", "public, max-age=86400")

	// Check to see if the client has this cached on their side.
	ifNoneMatch := r.Header.Get("If-None-Match")
	itm := memcache.NewItem(c, mkey)
	if ifNoneMatch != "" {
		err := memcache.Get(c, itm)
		if err == nil && r.Header.Get("If-None-Match") == string(itm.Value()) {
			w.WriteHeader(http.StatusNotModified)
			return
		}
	}

	contents, err := getZipFile(c, builder, buildNum, filepath)
	if err != nil {
		panic(err)
	}

	if contents == nil {
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte("not found"))
		return
	}

	h := sha256.New()
	h.Write(contents)
	itm.SetValue([]byte(fmt.Sprintf("%x", h.Sum(nil))))
	err = memcache.Set(c, itm)
	if err != nil {
		logging.Warningf(c, "Error while setting memcache key for etag digest: %v", err)
	} else {
		w.Header().Set("ETag", string(itm.Value()))
	}

	// The order of these statements matters. See net/http docs for more info.
	w.Header().Set("Content-Type", http.DetectContentType(contents))
	w.WriteHeader(http.StatusOK)
	w.Write(contents)
}

const megabyte = 1 << 20

// Amount of data to fetch from GCS. URL Fetch requests must be smaller than 32 MB.
const chunkSize = megabyte * 31

// knownPrefixes is a list of strings that we know will exist in the google storage bucket.
// If the first path element in the filepath is not on this list, it's assumed to be a substep,
// and the zip file in that subdirectory is used, instead of at the root of the build number bucket.
var knownPrefixes = []string{
	"layout-test-results",
	"retry_summary.json",
}

// itmForStringHash returns a memcache item for a given key. It hashes the key
// to make sure that it'll fit into the memcache length limits.
func itmForStringHash(c context.Context, key string) memcache.Item {
	h := sha256.New()
	h.Write([]byte(key))
	return memcache.NewItem(c, fmt.Sprintf("%x", h.Sum(nil)))
}

// getZipFile retrieves a file from a layout test archive for a build number from a builder.
var getZipFile = func(c context.Context, builder, buildNum, filepath string) ([]byte, error) {
	prefix := ""
	found := false
	for _, prefix := range knownPrefixes {
		if strings.HasPrefix(filepath, prefix) {
			found = true
		}
	}

	if !found && strings.Contains(filepath, "/") {
		prefix = strings.Split(filepath, "/")[0] + "/"
		filepath = strings.Join(strings.Split(filepath, "/")[1:], "/")
	}
	gsPath := gs.Path(fmt.Sprintf("gs://chromium-layout-test-archives/%s/%s/%slayout-test-results.zip", builder, buildNum, prefix))

	itm := itmForStringHash(c, fmt.Sprintf("%s|%s", gsPath, filepath))
	err := memcache.Get(c, itm)
	if err != memcache.ErrCacheMiss && err != nil {
		logging.Warningf(c, "memcache.Get error for requested file %v: %v", itm.Key(), err)
	}

	logging.Debugf(c, "Getting google storage path %s filepath %s", gsPath, filepath)
	if err == memcache.ErrCacheMiss || len(itm.Value()) == 0 {
		zr, err := readZipFile(c, gsPath)
		if err != nil {
			return nil, fmt.Errorf("while reading zip file: %v", err)
		}

		if zr == nil {
			logging.Errorf(c, "got a nil zip file for %v", gsPath)
			// Effectively a 404
			return nil, nil
		}

		// If we're serving the results.html file, we expect users to want to look at
		// the failed test artifacts. Cache these.
		if strings.Contains(filepath, "results.html") {
			if err := cacheFailedTests(c, zr, string(gsPath)); err != nil {
				logging.Warningf(c, "while caching failed tests: %v", err)
			}
		}

		for _, f := range zr.File {
			if f.Name == filepath {
				freader, err := f.Open()
				if err != nil {
					return nil, fmt.Errorf("while opening zip file: %v", err)
				}

				res, err := ioutil.ReadAll(freader)
				if err != nil {
					return nil, err
				}
				itm.SetValue(res)
				break
			}
		}

		logging.Debugf(c, "main item caching stats: len %v limit %v", len(itm.Value()), megabyte/2)
		if itm.Value() != nil && len(itm.Value()) < megabyte/2 {
			logging.Debugf(c, "setting %s", itm.Key())
			if err := memcache.Set(c, itm); err != nil {
				logging.Warningf(c, "memcache.Set error for requested file %v: %v", filepath, err)
			}
		}
	}

	return itm.Value(), nil
}

// cacheFailedTests caches the failed tests stored in the resulting zip file.
// gsPath is used to construct the memcache keys as needed.
func cacheFailedTests(c context.Context, zr *zip.Reader, gsPath string) error {
	// First, read the results file to find a list of failed tests.
	failedTests := []string{}
	for _, f := range zr.File {
		if f.Name == "layout-test-results/full_results.json" {
			freader, err := f.Open()
			if err != nil {
				return err
			}

			fullResultsDat, err := ioutil.ReadAll(freader)
			if err != nil {
				return err
			}
			failedTests = getFailedTests(c, fullResultsDat)
			break
		}
	}
	if len(failedTests) == 0 {
		return nil
	}

	logging.Debugf(c, "caching artifacts for %v failed tests", len(failedTests))
	toPut := []memcache.Item{}
	for _, f := range zr.File {
		// If we have too many test failures, we try to cache too much data and OOM,
		// and the instance service the request runs out of memory. Just give up after
		// some number of failures for now.
		if len(toPut) > 500 {
			break
		}
		// I tried using goroutines to make this concurrent, but it seemed to be slower.
		for _, test := range failedTests {
			// Ignore retried results, results.html doesn't seem to fetch them
			byPath := strings.Split(f.Name, "/")
			if len(byPath) > 2 && strings.Contains(byPath[1], "retry") {
				break
			}
			if strings.Contains(f.Name, test) {
				newItm := itmForStringHash(c, fmt.Sprintf("%s|%s", gsPath, f.Name))
				freader, err := f.Open()
				if err != nil {
					logging.Warningf(c, "failed in result caching: %v", err)
					continue
				}

				res, err := ioutil.ReadAll(freader)
				if err != nil {
					logging.Warningf(c, "failed in result caching: %v", err)
					continue
				}
				newItm.SetValue(res)
				toPut = append(toPut, newItm)
			}
		}
	}
	return memcache.Set(c, toPut...)
}

// Tests are named like url-format-any.html. Test artifacts are named like
// url-format-any-diff.png. To check if a test artifact should be cached, we do
// a string.Contains(test, test_artifact). To make this match, we need to strip
// the file extension from the test.
var knownTestArtifactExtensions = []string{
	"html", "svg", "xml", "js",
}

// Gets a list of failed tests from a full results json file.
var getFailedTests = func(c context.Context, fullResultsBytes []byte) []string {
	fr := model.FullResult{}
	err := json.Unmarshal(fullResultsBytes, &fr)
	if err != nil {
		panic(err)
	}
	flattened := fr.Tests.Flatten("/")
	names := []string{}

	for name, test := range flattened {
		if len(test.Actual) != len(test.Expected) {
			continue
		}
		if test.Unexpected == nil || !*test.Unexpected {
			continue
		}
		ue := unexpected(test.Expected, test.Actual)

		hasPass := false
		// If there was a pass at all, count it.
		for _, r := range test.Actual {
			if r == "PASS" {
				hasPass = true
			}
		}

		if len(ue) > 0 && !hasPass {
			for _, suffix := range knownTestArtifactExtensions {
				if strings.HasSuffix(name, "."+suffix) {
					name = name[:len(name)-len("."+suffix)]
				}
			}
			names = append(names, name)
		}
	}
	return names
}

// unexpected returns the set of expected xor actual.
func unexpected(expected, actual []string) []string {
	e, a := make(map[string]bool), make(map[string]bool)
	for _, s := range expected {
		e[s] = true
	}
	for _, s := range actual {
		a[s] = true
	}

	ret := []string{}

	// Any value in the expected set is a valid test result.
	for k := range a {
		if !e[k] {
			ret = append(ret, k)
		}
	}

	return ret
}

// streamingGSReader streams reads
type streamingGSReader struct {
	cl    gs.Client
	path  gs.Path
	c     context.Context
	cache map[int64][]byte
}

func (s *streamingGSReader) ReadAt(p []byte, off int64) (n int, err error) {
	if len(p) > chunkSize {
		// I've never seen the zip package request anything this large, but just in case...
		panic(fmt.Sprintf("bad size %v > %v", len(p), chunkSize))
	}

	for offset, dat := range s.cache {
		if offset <= off && offset+int64(len(dat)) >= off+int64(len(p)) {
			relativeOff := off - offset
			return copy(p, dat[relativeOff:relativeOff+int64(len(p))]), nil
		}
	}

	logging.Infof(s.c, "caching read for %v bytes %v + %v", s.path, off, len(p))
	r, err := s.cl.NewReader(s.path, off, chunkSize)
	if err != nil && err != storage.ErrObjectNotExist {
		return 0, fmt.Errorf("while creating reader: %v", err)
	}
	if err == storage.ErrObjectNotExist {
		return 0, fmt.Errorf("object not found: %v", s.path)
	}
	readBytes, err := ioutil.ReadAll(r)
	if err != nil {
		return 0, fmt.Errorf("while reading bytes: %v", err)
	}
	s.cache[off] = readBytes
	return copy(p, readBytes), nil
}

// Reads the zip file at the given google storage path. If the file isn't found, returns nil for the reader.
var readZipFile = func(c context.Context, gsPath gs.Path) (*zip.Reader, error) {
	transport, err := auth.GetRPCTransport(c, auth.NoAuth)
	if err != nil {
		return nil, fmt.Errorf("while creating transport: %v", err)
	}

	cl, err := gs.NewProdClient(c, transport)
	if err != nil {
		return nil, fmt.Errorf("while creating client: %v", err)
	}

	// Get total size
	attrs, err := cl.Attrs(gsPath)
	if err != nil && err != storage.ErrObjectNotExist {
		return nil, fmt.Errorf("while reading file size: %v", err)
	}
	if err == storage.ErrObjectNotExist {
		return nil, nil
	}

	// This code used to fetch the whole file at once, but it turns out just doing
	// a streaming reader is faster for every case that I tested.
	zr, err := zip.NewReader(&streamingGSReader{
		cl:    cl,
		path:  gsPath,
		c:     c,
		cache: map[int64][]byte{},
	}, attrs.Size)
	if err != nil {
		return nil, fmt.Errorf("while creating zip reader: %v", err)
	}
	return zr, nil
}
