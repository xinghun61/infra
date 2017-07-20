package som

import (
	"fmt"
	"net/http"
	"net/url"
	"strconv"

	"infra/monitoring/client"
	"infra/monitoring/messages"

	"github.com/aryann/difflib"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"

	"bytes"
	"compress/zlib"
	"encoding/json"
)

const (
	productionAnalyticsID = "UA-55762617-1"
)

var (
	logdiffSize = metric.NewInt("sheriff_o_matic/analyzer/logdiff_size", "logdiff size over time", nil, field.String("tree"))
)

// LogDiff is the entity that will be stored in datastore.
type LogDiff struct {
	// Diffs is the log diff object that will be used to construct the logdiff page.
	Diffs []byte `gae:",noindex"`
	// Master is the master name of these logs.
	Master string
	// Builder is the builder name of these logs.
	Builder string
	// BuildNum1 is the build number of the first log to be diffed.
	BuildNum1 int64
	// BuildNum2 is the build number of the second log to be diffed.
	BuildNum2 int64
	// ID is for GAE purpose
	ID int64 `gae:"$id"`
	// Complete is recording completeness
	Complete bool
}

type logerr struct {
	log []string
	err error
}

// LogDiffJSONHandler will write log diff JSON as an API.
func LogDiffJSONHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params
	master := p.ByName("master")
	builder := p.ByName("builder")
	lo1, err := strconv.Atoi(p.ByName("buildNum1"))
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	lo2, err := strconv.Atoi(p.ByName("buildNum2"))
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	buildNum1 := int64(lo1)
	buildNum2 := int64(lo2)
	var diffs []*LogDiff
	q := datastore.NewQuery("LogDiff")
	q = q.Limit(1)
	q = q.Eq("Master", master).Eq("Builder", builder).Eq("BuildNum1", buildNum1).Eq("BuildNum2", buildNum2)
	err = datastore.GetAll(c, q, &diffs)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error retrieving diffs from datastore: %v", err))
		return
	}
	if len(diffs) <= 0 {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("Can't find specified logdiff"))
		return
	}

	if !diffs[0].Complete {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("Diff file in progress"))
		return
	}
	data := diffs[0].Diffs
	buffer := bytes.NewBuffer(data)
	reader, err := zlib.NewReader(buffer)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error decompressing logdiff: %v", err))
		return
	}
	tmp := new(bytes.Buffer)
	tmp.ReadFrom(reader)
	reader.Close()

	w.Header().Set("Content-Type", "application/json")
	w.Write(tmp.Bytes())
}

// LogdiffWorker is performing diff and storing on tasks in logdiff queue.
func LogdiffWorker(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	master := r.FormValue("master")
	builder := r.FormValue("builder")
	lastPass := r.FormValue("lastPass")
	lastFail := r.FormValue("lastFail")
	masURL, err := url.Parse(master)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error parsing url: %v", err))
		return
	}
	Master := &messages.MasterLocation{URL: *masURL}
	lo1, err := strconv.Atoi(lastFail)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	lo2, err := strconv.Atoi(lastPass)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	buildNum1 := int64(lo1)
	buildNum2 := int64(lo2)
	reader := client.GetReader(c)
	if reader == nil {
		transport, err := auth.GetRPCTransport(c, auth.AsSelf)
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error getting transport: %v", err))
			return
		}
		c = urlfetch.Set(c, transport)

		miloReader := client.GetMilo(c)

		memcachingReader := client.NewMemcacheReader(miloReader)
		c = client.WithReader(c, memcachingReader)
	}
	logchan := make(chan *logerr)
	go func() {
		ret, err := client.StdioForStep(c, Master, builder, "steps", buildNum1)
		logchan <- &logerr{
			log: ret,
			err: err,
		}
	}()
	res2, err := client.StdioForStep(c, Master, builder, "steps", buildNum2)

	res1 := <-logchan

	if res1.err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error fetching log: %v", res1.err))
		return
	}
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error fetching log: %v", err))
		return
	}
	diffs := difflib.Diff(res1.log, res2)
	merged := mergeLines(diffs)

	data, err := json.Marshal(merged)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error marshaling JSON for logdiff: %v", err))
		return
	}

	var buffer bytes.Buffer
	writer := zlib.NewWriter(&buffer)
	writer.Write(data)
	writer.Close()

	stringID := r.FormValue("ID")
	id, err := strconv.Atoi(stringID)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error converting string to integer: %v", err))
		return
	}
	diff := &LogDiff{ID: int64(id)}
	if err := datastore.Get(c, diff); err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error getting Logdiff shell: %v", err))
		return
	}
	diff.Diffs = buffer.Bytes()
	diff.Complete = true
	logdiffSize.Set(c, int64(len(diff.Diffs)), "chromium")
	err = datastore.Put(c, diff)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error storing Logdiff: %v", err))
		return
	}
}

// mergeLines will return a new diff where adjacent records with the same diff type are merged into one
func mergeLines(diffs []difflib.DiffRecord) []difflib.DiffRecord {
	if diffs == nil {
		return nil
	}
	var merged []difflib.DiffRecord
	// iterate through the lines
	for i := 0; i < len(diffs); {
		// simply copy it if it is the last record in the slice
		if i == len(diffs)-1 {
			merged = append(merged, diffs[i])
			break
		}
		j := 1
		curr := diffs[i]
		for diffs[i+j].Delta == diffs[i].Delta {
			// iteratively build a string that represents the merged line
			curr.Payload += "\n" + diffs[i+1].Delta.String() + " " + diffs[i+j].Payload
			j++
			// stop if the end is reached
			if i+j == len(diffs) {
				break
			}
		}
		// append the merged line
		merged = append(merged, curr)
		// go to the next unmerged line
		i += j
	}
	return merged
}
