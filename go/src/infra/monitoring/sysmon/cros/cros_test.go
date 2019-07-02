package cros

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/tsmon"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestUpdate(t *testing.T) {
	now := time.Date(2000, 1, 2, 3, 4, 5, 0, time.UTC)
	c := context.Background()
	c, _ = tsmon.WithDummyInMemory(c)
	c, _ = testclock.UseTime(c, now)
	Convey("In a temporary directory", t, func() {
		tmpPath, err := ioutil.TempDir("", "cros-devicefile-test")
		So(err, ShouldBeNil)
		defer os.RemoveAll(tmpPath)
		fileNames := []string{
			strings.Replace(fileGlob, "*", "device1", 1),
			strings.Replace(fileGlob, "*", "device2", 1),
			strings.Replace(fileGlob, "*", "device3", 1),
		}
		Convey("Loads a number of empty files", func() {
			for _, fileName := range fileNames {
				err := ioutil.WriteFile(filepath.Join(tmpPath,
					fileName), []byte(""), 0644)
				So(err, ShouldBeNil)
			}
			err = update(c, tmpPath)
			So(err, ShouldNotBeNil)
		})
		Convey("Loads a number of broken files", func() {
			for _, fileName := range fileNames {
				err := ioutil.WriteFile(filepath.Join(tmpPath,
					fileName), []byte(`not json`), 0644)
				So(err, ShouldBeNil)
			}
			err = update(c, tmpPath)
			So(err, ShouldNotBeNil)
		})
	})
}

func TestUpdateMetrics(t *testing.T) {
	now := time.Date(2000, 1, 2, 3, 4, 5, 0, time.UTC)
	c := context.Background()
	c, _ = tsmon.WithDummyInMemory(c)
	c, _ = testclock.UseTime(c, now)
	statusFile := deviceStatusFile{
		ContainerHostname: "b1_b2",
		Timestamp:         946782246,
		Status:            "online",
	}
	Convey("UpdateMetrics Testing", t, func() {
		updateMetrics(c, statusFile)
		So(dutStatus.Get(c, statusFile.ContainerHostname), ShouldEqual,
			"online")
	})
}
