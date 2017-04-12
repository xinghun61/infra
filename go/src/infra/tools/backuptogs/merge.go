package main

// merges two channels to a single channel, which is an oddly complex operation, which is why
// this has been given it's own goroutine.
// Note that the alternative approach would be to have a single write channel shared by two
// goroutines, but that would require coordinating shutdown of the goroutines and closing of
// the channel, which could risk writing to a closed channel and causing a panic.
func mergeFileInfoChans(c1 <-chan fileInfo, c2 <-chan fileInfo) <-chan fileInfo {
	merged := make(chan fileInfo, 10)

	go func() {
		for i := 2; i > 0; {
			select {
			case f1, ok := <-c1:
				if !ok {
					c1 = nil
					i--
					continue
				}
				merged <- f1
			case f2, ok := <-c2:
				if !ok {
					c2 = nil
					i--
					continue
				}
				merged <- f2
			}
		}
		close(merged)
	}()

	return merged
}
