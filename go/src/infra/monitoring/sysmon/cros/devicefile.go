package cros

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"time"

	"go.chromium.org/luci/common/clock"
	"golang.org/x/net/context"
)

const (
	maxStaleness = time.Second * 160
	fileGlob     = "*_cros_device_status.json"
)

// deviceStatusFile is the contents of ~/*cros_device_status.json file, but
// only the fields we care about
type deviceStatusFile struct {
	ContainerHostname string  `json:"container_hostname"`
	Timestamp         float64 `json:"timestamp"`
	Status            string  `json:"status"`
}

func loadfile(c context.Context, path string) (df deviceStatusFile, err error) {
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return
	}
	err = json.Unmarshal(data, &df)
	if err != nil {
		return
	}
	ts := time.Unix(0, int64(df.Timestamp*float64(time.Second)))
	now := clock.Now(c)
	staleness := now.Sub(ts)
	if staleness >= maxStaleness {
		err = fmt.Errorf(
			"Device status file is stale. Last update %v ago",
			staleness)
	}
	return
}
