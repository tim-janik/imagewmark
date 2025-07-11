# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

all:		# Default Rule
MAKEFLAGS	 += -r
SHELL		::= /bin/bash -o pipefail
CLEANFILES	::=
S ::= # Variable containing 1 space
S +=
Q		::= $(if $(findstring 1, $(V)),, @)
QSKIP		::= $(if $(findstring s,$(MAKEFLAGS)),: )
QECHO		  = @QECHO() { Q1="$$1"; shift; QR="$$*"; QOUT=$$(printf '  %-8s ' "$$Q1" ; echo "$$QR") && $(QSKIP) echo "$$QOUT"; }; QECHO
QGEN		  = $(QECHO) GEN $@
CXX		 ?= clang++
CXXSTD		::= -std=gnu++17
CXXFLAGS	::= -Wall -O3 -g
LDLIBS		::= -lOpenImageIO -lOpenImageIO_Util -lgcrypt
CCACHE		 ?= $(if $(CCACHE_DIR), ccache)

include $(wildcard ./*.d ./*/*.d)

# == autocfg.hh ==
autocfg.hh: # Makefile
	$(QGEN)
	$Q echo						 > $@.tmp
	$(QECHO) DETECT libopenimageio-dev
	$Q grep -qF OPENIMAGEIO /usr/include/OpenImageIO/imageio.h
	$Q echo '#include <OpenImageIO/imageio.h>'	>> $@.tmp
	$(QECHO) DETECT libgcrypt20-dev
	$Q grep -qF gcry_cipher_open /usr/include/gcrypt.h
	$Q echo '#include <gcrypt.h>'			>> $@.tmp
	$Q mv $@.tmp $@
CLEANFILES += autocfg.hh

# == Implicit Rules ==
compiledefs     = $(DEFS) $(EXTRA_DEFS) $($<.DEFS) $($@.DEFS) $(INCLUDES) $(EXTRA_INCLUDES) $($<.INCLUDES) $($@.INCLUDES)
compilecxxflags = $(CXXFLAGS) $(EXTRA_FLAGS) $($<.FLAGS) $($@.FLAGS) -MQ '$@' -MMD -MF '$@'.d
%.o: %.cc autocfg.hh
	$(QECHO) CXX $@
	$Q $(CCACHE) $(CXX) $(CXXSTD) -fPIC $(compiledefs) $(compilecxxflags) -o $@ -c $<
CLEANFILES += *.o *.o.d

# == imagewmark-cxx ==
imagewmark-cxx.sources = imagewmark.cc utils.cc random.cc convcode.cc
imagewmark-cxx.objects = $(imagewmark-cxx.sources:.cc=.o)
imagewmark-cxx: $(imagewmark-cxx.objects)
	$(QECHO) LD $@
	$Q $(CXX) $(CXXSTD) -fPIC -o $@ $(LDFLAGS) $(imagewmark-cxx.objects) $(LDLIBS) -Wl,--print-map >$@.map
CLEANFILES += imagewmark-cxx imagewmark-cxx.map
all: imagewmark-cxx

# == Clean ==
clean:
	rm -f $(CLEANFILES)

# == Check ==
check: test-image-comment
	./imagewmark-cxx convcode-check

# == Tests ==
test-image-comment: imagewmark-cxx
	$(QECHO) CHECK $@
	$Q convert -size 320x200 -gravity center -pointsize 72 label:Test test1.png
	$Q ./imagewmark-cxx ADD test1.png test1w.png affe0007f00dbeef >test1w.out
	$Q ./imagewmark-cxx GET test1w.png >test1w.out
	$Q grep -q '^message: affe0007f00dbeef' test1w.out
	$Q rm -f test1.png test1w.png test1w.out
