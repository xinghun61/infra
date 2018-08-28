package autotest

import (
	"bytes"
	"reflect"
	"testing"
)

func TestWriteKeyvals(t *testing.T) {
	t.Parallel()
	var b bytes.Buffer
	m := map[string]string{
		"foo": "bar",
	}
	err := WriteKeyvals(&b, m)
	if err != nil {
		t.Errorf("WriteKeyvals returned error: %+v", err)
	}
	exp := "foo=bar\n"
	s := b.String()
	if !reflect.DeepEqual(s, exp) {
		t.Errorf("Got %#v, expected %#v", s, exp)
	}
}
