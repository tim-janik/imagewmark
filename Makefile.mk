# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
all:	# default target

SHELL		:= /bin/bash -o pipefail
version_full	!= src/version.sh
VERSION		:= $(word 1, $(version_full))
version_bits	:= $(subst _, , $(subst -, , $(subst ., , $(VERSION))))
PKGVERSION	:= $(word 1, $(version_bits)).$(word 2, $(version_bits))
ALL_TARGETS	:=
Q		:= $(if $(findstring 1, $(V)),, @)
QGEN		 = @echo '  GEN     ' $@
QSKIP		:= $(if $(findstring s,$(MAKEFLAGS)),: )
QECHO		 = @QECHO() { Q1="$$1"; shift; QR="$$*"; QOUT=$$(printf '  %-8s ' "$$Q1" ; echo "$$QR") && $(QSKIP) echo "$$QOUT"; }; QECHO
QCHECK		 = $(QECHO) CHECK $@
QOK		 = $(QECHO) OK $@
PANDOC		:= pandoc
CLEANDIRS	:=
CLEANFILES	 = $(ALL_TARGETS) .version

# == Paths ==
# Installation locations
PREFIX	?= /usr/local
BINDIR	?= $(PREFIX)/bin
LIBEXEC	?= libexec/imagewmark-$(PKGVERSION)
PRJDIR	?= $(PREFIX)/$(LIBEXEC)

# == Versioning ==
# Force .version to be kept up to date
.version: ; $(QGEN) && src/version.sh > $@
ALL_TARGETS += .version
ifneq ($(version_full),$(shell test ! -r .version || cat .version))
.PHONY: .version
endif

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
	cp -Pp imagewmark .version $(PRJDIR)
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

# == distcheck ==
distcheck:
	@$(eval distversion != git describe --match='v[0-9]*.[0-9]*.[0-9]*' | sed 's/^v//')
	@$(eval distname := imagewmark-$(distversion))
	$(QECHO) MAKE $(distname).tar.zst
	$Q test -n "$(distversion)" || { echo -e "#\n# $@: ERROR: no dist version, is git working?\n#" >&2; false; }
	$Q git describe --dirty | grep -qve -dirty || echo -e "#\n# $@: WARNING: working tree is dirty\n#"
	$Q rm -r -f artifacts/ && mkdir -p artifacts/
	$Q # Generate ChangeLog with ^^-prefixed records. Tab-indent commit bodies, kill whitespaces and multi-newlines
	$Q git log --abbrev=13 --date=short --first-parent HEAD	\
		--pretty='^^%ad  %an 	# %h%n%n%B%n'		>  artifacts/ChangeLog \
	&& sed 's/^/	/; s/^	^^// ; s/[[:space:]]\+$$// '	-i artifacts/ChangeLog \
	&& sed '/^\s*$$/{ N; /^\s*\n\s*$$/D }'			-i artifacts/ChangeLog
	$Q # Generate and compress artifacts/*.tar.zst
	$Q git archive --prefix=$(distname)/ --add-file artifacts/ChangeLog -o artifacts/$(distname).tar HEAD
	$Q zstd --ultra -22 --rm artifacts/$(distname).tar && ls -lh artifacts/$(distname).tar.zst
	$Q T=`mktemp -d` && cd $$T && tar xf $(abspath artifacts/$(distname).tar.zst) \
	&& cd $(distname) \
	&& nice make all -j`nproc` \
	&& make PREFIX=$$T/inst install \
	&& make PREFIX=$$T/inst installcheck -j`nproc` \
	&& (set -x && $$T/inst/bin/imagewmark --version) \
	&& make PREFIX=$$T/inst uninstall \
	&& (set -x && $$PWD/imagewmark --version) \
	&& cd / && rm -r "$$T"
	$Q echo "Archive ready: artifacts/$(distname).tar.zst" | sed '1h; 1s/./=/g; 1p; 1x; $$p; $$x'
CLEANDIRS += artifacts/
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

# == check ==
check: check-syntax
.PHONY: check

# == all ==
all: $(ALL_TARGETS)
# Must be last rule
