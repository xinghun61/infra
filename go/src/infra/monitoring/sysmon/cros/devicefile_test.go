package cros

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/clock/testclock"
	"golang.org/x/net/context"
)

func TestLoadfile(t *testing.T) {
	now := time.Date(2000, 1, 2, 3, 4, 5, 0, time.UTC)
	c := context.Background()
	c, _ = testclock.UseTime(c, now)

	Convey("Using tmp directory", t, func() {
		// Use tmp dir to create a mock file
		path, err := ioutil.TempDir("", "cros-devicefile-test")
		So(err, ShouldBeNil)
		defer os.RemoveAll(path)

		fileName := filepath.Join(path, "file.json")

		Convey("loads a valid file", func() {
			err := ioutil.WriteFile(fileName, []byte(`{
			  "container_hostname": "b1_b2",
			  "status": "online",
			  "timestamp": 1559855998.093489
			}`), 0644)
			So(err, ShouldBeNil)
			f, err := loadfile(c, fileName)
			So(err, ShouldBeNil)
			So(f, ShouldResemble, deviceStatusFile{
				ContainerHostname: "b1_b2",
				Timestamp:         1559855998.093489,
				Status:            "online",
			})
		})

		Convey("file not found", func() {
			_, err := loadfile(c, "/file/not/found")
			So(err, ShouldNotBeNil)
		})

		Convey("invalid json", func() {
			err := ioutil.WriteFile(fileName,
				[]byte(`not valid json`), 0644)
			So(err, ShouldBeNil)

			_, err = loadfile(c, fileName)
			So(err, ShouldNotBeNil)
		})

	})
}
