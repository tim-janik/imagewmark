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
imagewmark:
	$(QGEN)
	$Q ln -sf src/imagewmark.py $@
ALL_TARGETS += imagewmark

# == install ==
install:
	$(QGEN)
	mkdir -p $(PRJDIR) $(PRJDIR)/src $(PRJDIR)/cxx
	cp -Pp imagewmark .version $(PRJDIR)
	cp -Pp src/*.py $(PRJDIR)/src
	cp -Pp cxx/cornersync cxx/peaks2grid cxx/imagewmark-cxx $(PRJDIR)/cxx
	ln -sf ../$(LIBEXEC)/imagewmark $(BINDIR)/imagewmark
uninstall:
	$(QGEN)
	rm -rf $(PRJDIR)
	test "$$(readlink -f $(BINDIR)/imagewmark)" != "$$(readlink -f $(PRJDIR)/imagewmark)" \
	|| rm -f $(BINDIR)/imagewmark

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

# == clean ==
clean:
	rm -f $(CLEANFILES)

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
