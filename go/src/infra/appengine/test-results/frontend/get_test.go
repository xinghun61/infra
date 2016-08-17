package frontend

import (
	"bytes"
	"io/ioutil"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestWrapCallback(t *testing.T) {
	t.Parallel()

	Convey("wrapCallback", t, func() {
		expected := []byte(`foo({"hello":"world"});`)
		result := wrapCallback(
			bytes.NewReader([]byte(`{"hello":"world"}`)),
			"foo",
		)
		b, err := ioutil.ReadAll(result)
		So(err, ShouldBeNil)
		So(b, ShouldResemble, expected)
	})
}
