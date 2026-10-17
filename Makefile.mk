# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
all:	# default target

SHELL		:= /bin/bash -o pipefail
version_info	!= grep -xm1 '^v\?[0-9][^$$]*' .version || git archive HEAD .version | tar -xOf -
TAG		:= $(word 1, $(version_info))
version_date	:= $(wordlist 2, 4, $(version_info))
version		 = $(patsubst v%,%,$(TAG))
version_bits	 = $(subst _, , $(subst -, , $(subst ., , $(version))))
PKGVERSION	 = $(word 1, $(version_bits)).$(word 2, $(version_bits))
ifeq ($(and $(word 3, $(version_bits)),$(word 4, $(version_info))),)
$(error Missing version information, need git describe or .version)
endif
ALL_TARGETS	:=
Q		:= $(if $(findstring 1, $(V)),, @)
QGEN		 = @echo '  GEN     ' $@
QSKIP		:= $(if $(findstring s,$(MAKEFLAGS)),: )
QECHO		 = @QECHO() { Q1="$$1"; shift; QR="$$*"; QOUT=$$(printf '  %-8s ' "$$Q1" ; echo "$$QR") && $(QSKIP) echo "$$QOUT"; }; QECHO
QCHECK		 = $(QECHO) CHECK $@
QOK		 = $(QECHO) OK $@
PANDOC		:= pandoc
CLEANDIRS	:=
CLEANFILES	 = $(ALL_TARGETS)

# == Paths ==
# Installation locations
PREFIX	?= /usr/local
BINDIR	?= $(PREFIX)/bin
LIBEXEC	?= libexec/imagewmark-$(PKGVERSION)
PRJDIR	?= $(PREFIX)/$(LIBEXEC)

# == Versioning ==
version:
	@echo "$(version)  $(version_date)"
.PHONY: version

# == Subdir Makefiles ==
include src/Makefile.mk
include cxx/Makefile.mk
include doc/Makefile.mk

# Rules
imagewmark: cxx/imagewmark
	$(QGEN)
	$Q ln -sf cxx/imagewmark $@
ALL_TARGETS += imagewmark

# == install ==
install:
	$(QGEN)
	mkdir -p $(BINDIR) $(PRJDIR) $(PRJDIR)/src $(PRJDIR)/cxx $(PRJDIR)/doc $(PREFIX)/share/man/man1
	cp -Pp imagewmark $(PRJDIR)
	echo '$(version_info)' > $(PRJDIR)/.version
	cp -Pp src/*.py $(PRJDIR)/src
	cp -Pp cxx/cornersync cxx/peaks2grid cxx/imagewmark cxx/wmops $(PRJDIR)/cxx
	cp -Pp doc/imagewmark.1 doc/imagewmark-arch.html $(PRJDIR)/doc
	ln -sf ../../../$(LIBEXEC)/doc/imagewmark.1 $(PREFIX)/share/man/man1/imagewmark-$(PKGVERSION).1
	ln -sf imagewmark-$(PKGVERSION).1 $(PREFIX)/share/man/man1/imagewmark.1
	ln -sf ../$(LIBEXEC)/imagewmark $(BINDIR)/imagewmark-$(PKGVERSION)
	ln -sf imagewmark-$(PKGVERSION) $(BINDIR)/imagewmark
uninstall:
	$(QGEN)
	test "$$(readlink $(BINDIR)/imagewmark)" != "imagewmark-$(PKGVERSION)" \
	|| rm -f $(BINDIR)/imagewmark $(PREFIX)/share/man/man1/imagewmark.1
	test "$$(readlink -f $(BINDIR)/imagewmark-$(PKGVERSION))" != "$$(readlink -f $(PRJDIR)/imagewmark)" \
	|| rm -f $(BINDIR)/imagewmark-$(PKGVERSION) $(PREFIX)/share/man/man1/imagewmark-$(PKGVERSION).1
	rm -rf $(PRJDIR)

# == installcheck ==
# verify that the installed imagewmark can process WMs
INSTALLED_IMAGEWMARK := $(PRJDIR)/imagewmark
installcheck:
	@$(eval TDIR != mktemp --tmpdir -d iwm.XXXXXX)
	$(QGEN)
	$Q convert tests/example01.svg $(TDIR)/iwmtest01.png
	$Q cd $(TDIR) && $(INSTALLED_IMAGEWMARK) add iwmtest01.png iwmtest01wm.png 1234abcd00
	$Q cd $(TDIR) && $(INSTALLED_IMAGEWMARK) get --cornersync=on  iwmtest01wm.png >wm-cs.out && fgrep -q 1234abcd00 wm-cs.out
	$Q cd $(TDIR) && $(INSTALLED_IMAGEWMARK) get --cornersync=off iwmtest01wm.png >wm-nc.out && fgrep -q 1234abcd00 wm-nc.out
	$Q rm -r $(TDIR)

# == dist ==
# DIST_VERSION overrides the release version, e.g. a nightly tag plus -g<hash>; dist bakes it into .version.
dist:
	$(eval TAG := $(or $(DIST_VERSION),$(TAG)))
	$(eval version_info := $(TAG) $(version_date))
	$(eval distname := imagewmark-$(version))
	$(QECHO) MAKE $(distname).tar.zst
	$Q git describe --dirty | grep -qve -dirty || echo -e "#\n# $@: WARNING: working tree is dirty\n#"
	$Q rm -r -f artifacts/ && mkdir -p artifacts/ && echo '$(version_info)' > artifacts/.version
	$Q # Generate ChangeLog with ^^-prefixed records. Tab-indent commit bodies, kill whitespaces and multi-newlines
	$Q git log --abbrev=13 --date=short --first-parent HEAD	\
		--pretty='^^%ad  %an 	# %h%n%n%B%n'		>  artifacts/ChangeLog \
	&& sed 's/^/	/; s/^	^^// ; s/[[:space:]]\+$$// '	-i artifacts/ChangeLog \
	&& sed '/^\s*$$/{ N; /^\s*\n\s*$$/D }'			-i artifacts/ChangeLog
	$Q # Generate and compress artifacts/*.tar.zst
	$Q git archive --prefix=$(distname)/ --add-file artifacts/ChangeLog --add-file artifacts/.version -o artifacts/$(distname).tar HEAD ':!.version'
	$Q zstd --ultra -22 --rm artifacts/$(distname).tar && ls -lh artifacts/$(distname).tar.zst
	$Q echo "Archive ready: artifacts/$(distname).tar.zst" | sed '1h; 1s/./=/g; 1p; 1x; $$p; $$x'
CLEANDIRS += artifacts/
.PHONY: dist

# == distcheck ==
# Build and test all release files from a fresh source tarball.
distcheck: dist
	@$(eval distname := imagewmark-$(version))
	$(QECHO) CHECK $(distname).tar.zst
	$Q T=$$(mktemp --tmpdir -d imagewmark-distcheck-XXXXXXXX) \
	&& trap 'rm -rf "$$T"' EXIT \
	&& tar xf artifacts/$(distname).tar.zst -C $$T \
	&& cd $$T/$(distname) \
	&& $(MAKE) all -j$$(nproc) \
	&& $(MAKE) check -j$$(nproc) \
	&& test "$$(./imagewmark --version)" = "ImageWMark $(patsubst v%,%,$(version_info))" \
	&& $(MAKE) PREFIX=$$T/inst install \
	&& $(MAKE) PREFIX=$$T/inst installcheck \
	&& test "$$($$T/inst/bin/imagewmark --version)" = "ImageWMark $(patsubst v%,%,$(version_info))" \
	&& $(MAKE) PREFIX=$$T/inst uninstall \
	&& test ! -e $$T/inst/bin/imagewmark \
	&& test ! -e $$T/inst/$(LIBEXEC) \
	&& gzip -9c doc/imagewmark.1 > $(CURDIR)/artifacts/imagewmark.1.gz \
	&& cp -p doc/imagewmark-arch.html $(CURDIR)/artifacts/
	$Q cd artifacts/ \
	&& sha256sum $(distname).tar.zst ChangeLog imagewmark.1.gz imagewmark-arch.html > SHA256SUMS \
	&& sha256sum -c SHA256SUMS
	$Q echo "Distcheck ready: artifacts/$(distname).tar.zst" | sed '1h; 1s/./=/g; 1p; 1x; $$p; $$x'
.PHONY: distcheck

# == clean ==
clean:
	rm -f $(CLEANFILES)
	rm -f -r $(CLEANDIRS)

test:
	$(MAKE) -C tests/ $@
.PHONY: test

# == check-syntax ==
check-syntax:
	$(QECHO) CHECK 'Detect invalid print() statements'
	$Q { TCOLOR=--color=always ; tty -s <&1 || TCOLOR=; } \
	&& ( grep $$TCOLOR -nE '\bprint *\(' -r src/*.py || : )
.PHONY: check-syntax

# == check-formats ==
# Verify pixel format, alpha, CMYK and metadata handling of "imagewmark add"
tests/formats/check: imagewmark tests/formats/check-formats.sh tests/formats/check-metadata.py
	$(QCHECK)
	$Q tests/formats/check-formats.sh
	$(QOK)
.PHONY: tests/formats/check
check: tests/formats/check

# == check ==
FLAT_IMAGE_CHECKS := $(addprefix tests/check-flat-images-,black gray white)
$(FLAT_IMAGE_CHECKS): tests/check-flat-images-%: .version imagewmark cxx/wmops cxx/peaks2grid cxx/cornersync tests/check-flat-images.py
	$Q python3 tests/check-flat-images.py FlatImageTest.test_$*
	$(QOK)
tests/check-flat-images: $(FLAT_IMAGE_CHECKS)
.PHONY: tests/check-flat-images $(FLAT_IMAGE_CHECKS)
check: tests/check-flat-images

check: check-syntax
.PHONY: check

# == all ==
all: $(ALL_TARGETS)
# Must be last rule
