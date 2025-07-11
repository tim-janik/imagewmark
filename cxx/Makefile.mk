# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

CXX		?= clang++
CXXSTD		:= -std=gnu++17
CXXFLAGS	:= -Wall -O3 -g
LDLIBS		:= -lOpenImageIO -lOpenImageIO_Util -lgcrypt
LINK		 = $(CXX) $(CXXSTD) $(LDFLAGS)
CCACHE		?= $(if $(CCACHE_DIR), ccache)

# Dependency tracking
include $(wildcard ./*.d ./*/*.d)

# == C++ Rules ==
# == Implicit Rules ==
compiledefs     = $(DEFS) $(EXTRA_DEFS) $($<.DEFS) $($@.DEFS) $(INCLUDES) $(EXTRA_INCLUDES) $($<.INCLUDES) $($@.INCLUDES)
compilecxxflags = $(CXXFLAGS) $(EXTRA_FLAGS) $($<.FLAGS) $($@.FLAGS) -MQ $@ -MMD -MF $@.d
%.o: %.cc
	$(QECHO) CXX $@
	$Q $(CCACHE) $(CXX) $(CXXSTD) $(compiledefs) $(compilecxxflags) -o $@ -c $<
CLEANFILES += cxx/*.o cxx/*.o.d

# == cxx/imagewmark-cxx ==
cxx/imagewmark-cxx.sources = cxx/imagewmark.cc cxx/utils.cc cxx/random.cc cxx/convcode.cc
cxx/imagewmark-cxx.objects = $(cxx/imagewmark-cxx.sources:.cc=.o)
cxx/imagewmark-cxx: $(cxx/imagewmark-cxx.objects)
	$(QECHO) LD $@
	$Q $(LINK) $(cxx/imagewmark-cxx.objects) $(LDLIBS) -o $@ -Wl,--print-map >$@.map
ALL_TARGETS += cxx/imagewmark-cxx
CLEANFILES += cxx/imagewmark-cxx.map

# == Tests ==
cxx/test-image-comment: cxx/imagewmark-cxx
	$(QCHECK)
	$Q convert -size 320x200 -gravity center -pointsize 72 label:Test test1.png
	$Q cxx/imagewmark-cxx ADD test1.png test1w.png affe0007f00dbeef >test1w.out
	$Q cxx/imagewmark-cxx GET test1w.png >test1w.out
	$Q grep -q '^message: affe0007f00dbeef' test1w.out
	$Q rm -f test1.png test1w.png test1w.out
	$(QOK)
cxx/check: cxx/test-image-comment
cxx/test-convcode-check: cxx/imagewmark-cxx
	$(QCHECK)
	$Q cxx/imagewmark-cxx convcode-check
	$(QOK)
cxx/check: cxx/test-convcode-check
.PHONY: cxx/check cxx/test-convcode-check cxx/test-image-comment
check: cxx/check
