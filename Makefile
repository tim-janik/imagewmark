# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
all:	# default target

VERSION		:= 0.4.0

ALL_TARGETS	:=
Q		:= $(if $(findstring 1, $(V)),, @)
QGEN		 = @echo '  GEN     ' $@
QECHO		 = @QECHO() { Q1="$$1"; shift; QR="$$*"; QOUT=$$(printf '  %-8s ' "$$Q1" ; echo "$$QR") && echo "$$QOUT"; }; QECHO
PANDOC		:= pandoc
CLEANFILES	:=


include doc/Makefile.mk

all:
	$(MAKE) -C cxx $@
	$(MAKE) -C src $@
clean:
	$(MAKE) -C cxx $@
	$(MAKE) -C src $@
	rm -f $(CLEANFILES)

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

check:
	$(QECHO) Check 'Detect invalid print() statements'
	$Q { TCOLOR=--color=always ; tty -s <&1 || TCOLOR=; } \
	&& ( grep $$TCOLOR -nE '\bprint *\(' -r $(extract_files_py) || : )
	$(MAKE) -C cxx $@
	$(MAKE) -C src $@

all: $(ALL_TARGETS)
