package frontend

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/memcache"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"

	"infra/appengine/test-results/buildextract"
	"infra/appengine/test-results/masters"
)

// BuilderData is the data returned from the GET "/builders"
// endpoint.
type BuilderData struct {
	Masters           []Master `json:"masters"`
	NoUploadTestTypes []string `json:"no_upload_test_types"`
}

// Master represents information about a build master.
type Master struct {
	Name       string          `json:"name"`
	Identifier string          `json:"url_name"`
	Groups     []string        `json:"groups"`
	Tests      map[string]Test `json:"tests"`
}

// Test represents information about Tests in a master.
type Test struct {
	Builders []string `json:"builders"`
}

const buildbotMemcacheKey = "buildbot_data"

var nonTestStepNames = []string{
	"archive",
	"Run tests",
	"find isolated tests",
	"read test spec",
	"Download latest chromedriver",
	"compile tests",
	"create_coverage_",
	"update test result log",
	"memory test:",
	"install_",
}

var noUploadTestSteps = []string{
	"java_tests(chrome",
	"python_tests(chrome",
	"run_all_tests.py",
	"test_report",
	"test CronetSample",
	"test_mini_installer",
	"webkit_python_tests",
}

func makeBuildExtractClient(ctx context.Context) *buildextract.Client {
	return buildextract.NewClient(&http.Client{
		Transport: urlfetch.Get(ctx),
	})
}

func getBuildersHandler(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	var res []byte
	item, err := memcache.Get(c).Get(buildbotMemcacheKey)

	switch err {
	case memcache.ErrCacheMiss:
		start := time.Now()
		data, err := getBuilderData(c, masters.Known, makeBuildExtractClient(c))
		if err != nil {
			logging.WithError(err).Errorf(c, "getBuildersHandler: getBuilderData")
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		logging.Fields{"duration": time.Since(start)}.Infof(c, "getBuildersHandler: getBuilderData")

		res, err = json.Marshal(&data)
		if err != nil {
			logging.WithError(err).Errorf(c, "getBuildersHandler: marshal JSON")
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		item.SetValue(res)
		if err := memcache.Get(c).Set(item); err != nil {
			// Log this error but do not return to the client because it is not critical
			// for this handler.
			logging.Fields{
				logging.ErrorKey: err,
				"item":           item,
			}.Errorf(c, "getBuildersHandler: set memcache")
		}

	case nil:
		res = item.Value()

	default:
		logging.WithError(err).Errorf(c, "getBuildersHandler")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	var out io.Reader = bytes.NewReader(res)
	if c := r.FormValue("callback"); callbackNameRx.MatchString(c) {
		out = wrapCallback(out, c)
	}

	n, err := io.Copy(w, out)

	if err != nil {
		logging.Fields{
			logging.ErrorKey: err,
			"n":              n,
		}.Errorf(c, "getBuildersHandler: error writing HTTP response")
	}
}

func updateBuildersHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	start := time.Now()
	data, err := getBuilderData(c, masters.Known, makeBuildExtractClient(c))
	if err != nil {
		logging.WithError(err).Errorf(c, "updateBuildersHandler: getBuilderData")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	logging.Fields{"duration": time.Since(start)}.Infof(c, "updateBuildersHandler: getBuilderData")

	b, err := json.Marshal(&data)
	if err != nil {
		logging.WithError(err).Errorf(c, "updateBuildersHandler: unmarshal JSON")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	item := memcache.Get(c).NewItem(buildbotMemcacheKey)
	item.SetValue(b)

	if err := memcache.Get(c).Set(item); err != nil {
		logging.WithError(err).Errorf(c, "updateBuildersHandler: set memcache")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	n, err := io.WriteString(w, "OK")

	if err != nil {
		logging.Fields{
			logging.ErrorKey: err,
			"n":              n,
		}.Errorf(c, "updateBuildersHandler: error writing HTTP response")
	}
}

func getBuilderData(ctx context.Context, list []*masters.Master, client buildextract.Interface) (BuilderData, error) {
	builderData := BuilderData{
		NoUploadTestTypes: noUploadTestSteps,
	}

	// Overview:
	// - For each master, start a goroutine that fetches
	//   the builder names for that master.
	// - For each of the builder names, fetch the step names
	//   for that master+builder combination.
	// - Once the step names for a master+builder combination
	//   arrive, update the Tests map on the master.
	// - Finally sort all the Builders fields in increasing order
	//   and remove duplicates.

	type result struct {
		Master Master
		Err    error
	}
	results := make(chan result, len(list))
	wg := sync.WaitGroup{}
	wg.Add(len(list))

	for _, master := range list {
		m := Master{
			Name:       master.Name,
			Identifier: master.Identifier,
			Groups:     master.Groups,
			Tests:      make(map[string]Test),
		}

		go func() {
			defer wg.Done()
			builders, err := getBuilderNames(ctx, m.Identifier, client)
			if err != nil {
				results <- result{Err: err}
				return
			}

			if len(builders) == 0 {
				return
			}

			for _, b := range builders {
				stepNames, err := getStepNames(ctx, m.Identifier, b, client)
				if err != nil {
					results <- result{Err: err}
					return
				}
				for _, s := range stepNames {
					t, ok := m.Tests[s]
					if !ok {
						t = Test{}
					}
					t.Builders = append(t.Builders, b)
					m.Tests[s] = t
				}
			}

			results <- result{Master: m}
		}()
	}

	wg.Wait()
	close(results)
	for res := range results {
		if res.Err != nil {
			logging.WithError(res.Err).Errorf(ctx, "getBuilderData")
			return BuilderData{}, res.Err
		}
		builderData.Masters = append(builderData.Masters, res.Master)
	}

	for _, m := range builderData.Masters {
		for key, test := range m.Tests {
			builders := sort.StringSlice(removeDuplicates(test.Builders))
			sort.Sort(builders)
			test.Builders = []string(builders)
			m.Tests[key] = test
		}
	}

	return builderData, nil
}

func removeDuplicates(list []string) []string {
	var ret []string
	seen := make(map[string]bool)

	for _, s := range list {
		if !seen[s] {
			seen[s] = true
			ret = append(ret, s)
		}
	}

	return ret
}

// getBuilderNames returns the builder names from Chrome
// build extracts for the supplied master.
func getBuilderNames(ctx context.Context, master string, client buildextract.Interface) ([]string, error) {
	r, err := client.GetMasterJSON(master)
	if err != nil {
		logging.Fields{
			logging.ErrorKey: err,
			"master":         master,
		}.Errorf(ctx, "getBuilderNames: GetMasterJSON")
		return nil, err
	}
	defer r.Close()

	data := struct {
		Builders map[string]struct{} `json:"builders"`
	}{}
	if err := json.NewDecoder(r).Decode(&data); err != nil {
		logging.Fields{
			logging.ErrorKey: err,
			"master":         master,
		}.Errorf(ctx, "getBuilderNames: unmarshal JSON")
		return nil, err
	}

	builders := make([]string, 0, len(data.Builders))
	for b := range data.Builders {
		builders = append(builders, b)
	}
	return builders, nil
}

// getStepNames returns the step names for the supplied master
// and builder from Chrome build extracts.
func getStepNames(ctx context.Context, master string, builder string, client buildextract.Interface) ([]string, error) {
	r, err := client.GetBuildsJSON(builder, master, 1)
	if err != nil {
		if se, ok := err.(*buildextract.StatusError); ok {
			if se.StatusCode == http.StatusNotFound {
				logging.Fields{
					"master": master, "builder": builder,
				}.Infof(ctx, "getStepNames: builds JSON not found")
				return nil, nil
			}
		}
		logging.Fields{
			logging.ErrorKey: err, "master": master, "builder": builder,
		}.Infof(ctx, "getStepNames")
		return nil, err
	}
	defer r.Close()

	data := struct {
		Builds []struct {
			Steps []struct {
				Name string `json:"name"`
			} `json:"steps"`
		} `json:"builds"`
	}{}
	if err := json.NewDecoder(r).Decode(&data); err != nil {
		logging.Fields{
			logging.ErrorKey: err, "master": master, "builder": builder,
		}.Errorf(ctx, "getStepNames: error unmarshaling JSON")
		return nil, err
	}
	if len(data.Builds) == 0 {
		logging.Fields{
			"master":  master,
			"builder": builder,
		}.Infof(ctx, "builders: empty build list")
		return nil, nil // Intentional: error is nil, simply skip this data.
	}

	var res []string
	for _, step := range data.Builds[0].Steps {
		name, ok := cleanTestStep(step.Name)
		if !ok {
			continue
		}
		res = append(res, name)
	}
	return res, nil
}

var ignoreTestNameRx = regexp.MustCompile(`_only|_ignore|_perf$`)
var gtestUploaderStepRx = regexp.MustCompile(`Upload to test-results \[([^]]*)\]`)

func cleanTestStep(name string) (clean string, ok bool) {
	if !strings.Contains(name, "test") {
		return "", false
	}

	for _, n := range nonTestStepNames {
		if strings.Contains(name, n) {
			return "", false
		}
	}

	if ignoreTestNameRx.MatchString(name) {
		return "", false
	}

	// Ignore triggering and collecting steps on swarming:
	// they are not actual tests.
	for _, p := range []string{"[trigger]", "[collect]", "[skipped]"} {
		if strings.HasPrefix(name, p) {
			return "", false
		}
	}

	if m := gtestUploaderStepRx.FindStringSubmatch(name); len(m) == 2 {
		name = m[1]
	}

	// The following comments are copied from the Python version. Evaluate
	// correctness of the TODO before working on it:
	//
	// Skip all steps that don't have test in the first word (before
	// the first space), and remove platform cruft. This rule is based
	// on a manual audit of valid and invalid test types populated in
	// the dashboard in Q4 2015.
	//
	// Normalization also happens at upload time to ensure known
	// and actual test types match.
	//
	// TODO: Remove nonTestStepNames since this rule should remove all
	// of them already.

	name = cleanTestType(name)
	return name, strings.Contains(name, "test")
}

func cleanTestType(name string) string {
	withPatch := false
	if strings.Contains(name, " (with patch)") {
		withPatch = true
		name = strings.Replace(name, " (with patch)", "", 1)
	}

	// Special rule for Instrumentation test.
	instr := "Instrumentation test "
	if strings.HasPrefix(name, instr) {
		name = name[len(instr):]
	}

	// Clean platform noise. For simplicity and based on current
	// data, we just keep everything before the first space.
	if i := strings.Index(name, " "); i != -1 {
		name = name[:i]
	}

	if withPatch {
		name += " (with patch)"
	}
	return name
}
