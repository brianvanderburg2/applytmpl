override SHELL:=/bin/bash
override SHELLOPTS:=errexit:pipefail
export SHELLOPTS
override DATE:=$(shell date -u "+%Y%m%d-%H%M")


.PHONY: check
check:

.PHONY: test
test: check

.PHONY: clean
clean: check
	rm -rf test/output
	rm -rf output

.PHONY: tarball
tarball: NAME:=applyconf-$(shell date +%Y%m%d)-$(shell git describe --always)
tarball: check clean
	mkdir -p output
	git archive --format=tar --prefix=$(NAME)/ HEAD | xz > output/$(NAME).tar.xz

