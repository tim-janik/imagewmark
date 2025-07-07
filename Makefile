# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
all:	# default target

version_full	!= src/version.sh
VERSION		:= $(word 1, $(version_full))
ALL_TARGETS	:=
Q		:= $(if $(findstring 1, $(V)),, @)
QGEN		 = @echo '  GEN     ' $@
QECHO		 = @QECHO() { Q1="$$1"; shift; QR="$$*"; QOUT=$$(printf '  %-8s ' "$$Q1" ; echo "$$QR") && echo "$$QOUT"; }; QECHO
PANDOC		:= pandoc
CLEANFILES	:=

# Installation locations
PREFIX	?= /usr/local
BINDIR	?= $(PREFIX)/bin
LIBEXEC	?= libexec/imagewmark-$(VERSION)
PRJDIR	?= $(PREFIX)/$(LIBEXEC)

# Force .version to be kept up to date
.version: ; src/version.sh > $@
Makefile: .version
ifneq ($(version_full),$(shell test ! -r .version || cat .version))
.PHONY: .version
endif

# Include subdirs
include doc/Makefile.mk

# Rules
imagewmark: ; ln -sf src/imagewmark.py $@
ALL_TARGETS += imagewmark

cxx/imagewmark-cxx: ; $(MAKE) -C cxx ${@:cxx/%=%}
ALL_TARGETS += cxx/imagewmark-cxx

src/peaks2grid: ; $(MAKE) -C src ${@:src/%=%}
ALL_TARGETS += src/peaks2grid

# == install ==
install:
	mkdir -p $(PRJDIR) $(PRJDIR)/src $(PRJDIR)/cxx
	cp -Pp imagewmark .version $(PRJDIR)
	cp -Pp src/*.py src/cornersync src/peaks2grid $(PRJDIR)/src
	cp -Pp cxx/imagewmark-cxx $(PRJDIR)/cxx
	ln -sf ../$(LIBEXEC)/imagewmark $(BINDIR)/imagewmark
uninstall:
	test "$$(readlink -f $(BINDIR)/imagewmark)" != "$$(readlink -f $(PRJDIR)/imagewmark)" \
	|| rm -f $(BINDIR)/imagewmark
	rm -rf $(PRJDIR)

# == clean ==
clean:
	$(MAKE) -C cxx $@
	$(MAKE) -C src $@
	rm -f $(CLEANFILES) ./imagewmark

test:
	$(MAKE) -C tests/ $@
.PHONY: test

extract_files_py = $(strip \
	src/common.py	\
	src/ddist.py	\
	src/extract.py	\
)
other_files_py = $(strip \
	src/config.py	\
	src/embed.py	\
	src/plotting.py	\
	src/wmtool.py	\
)

# == check ==
check: check-syntax check-cxx check-src
.PHONY: check
check-syntax:
	$(QECHO) CHECK 'Detect invalid print() statements'
	$Q { TCOLOR=--color=always ; tty -s <&1 || TCOLOR=; } \
	&& ( grep $$TCOLOR -nE '\bprint *\(' -r $(extract_files_py) || : )
.PHONY: check-syntax
check-cxx:
	$(MAKE) -C cxx check
.PHONY: check-cxx
check-src:
	$(MAKE) -C src check
.PHONY: check-src

# == all ==
all: $(ALL_TARGETS)
# Must be last rule
