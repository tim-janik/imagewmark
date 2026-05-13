# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

CXX		?= clang++
CXXSTD		:= -std=gnu++17
CXXFLAGS	:= -Wall -O3 -g
LDLIBS		:= -lOpenImageIO -lOpenImageIO_Util -lgcrypt
CXXDEPS		:=
LINK		 = $(CXX) $(CXXSTD) $(LDFLAGS)
CCACHE		?= $(if $(CCACHE_DIR), ccache)

# Dependency tracking
include $(wildcard ./*.d ./*/*.d)

# == OpenCV4 ==
cxx/opencv4.cflags != pkg-config --cflags opencv4
cxx/opencv4.libs   != pkg-config --libs opencv4
# Minimal required libs: cxx/opencv4.libs := -lgcrypt -lOpenImageIO -lopencv_core -lopencv_imgproc -lopencv_imgcodecs
ifeq ($(cxx/opencv4.cflags)$(cxx/opencv4.libs),)
$(error Failed to find OpenCV4 (opencv4.pc) via pkg-config)
endif

# == libvips ==
cxx/libvips.cflags != pkg-config --cflags vips-cpp
cxx/libvips.libs   != pkg-config --libs vips-cpp
ifeq ($(cxx/libvips.cflags)$(cxx/libvips.libs),)
$(error Failed to find libvips C++ bindings (vips-cpp.pc) via pkg-config)
endif

# == libcli11-dev ==
CLI11_VERSION	:= v2.6.2
CLI11_URL	:= 'https://github.com/CLIUtils/CLI11/releases/download/$(CLI11_VERSION)/CLI11.hpp'
CLI11_SHA256	:= 227a16fe5f9f8ada80c3c409492475536f597e7bd83a6c26eacc3c8c149a9295
cxx/3rdparty/CLI11/CLI11.hpp:
	$Q mkdir -p cxx/3rdparty/CLI11/
	$Q wget -O $@.tmp $(CLI11_URL)
	$Q echo "$(CLI11_SHA256)  $@.tmp" | sha256sum -c -
	$Q mv $@.tmp $@
CXXDEPS += cxx/3rdparty/CLI11/CLI11.hpp

# == C++ Rules ==
# == Implicit Rules ==
compiledefs     = $(DEFS) $(EXTRA_DEFS) $($<.DEFS) $($@.DEFS) $(INCLUDES) $(EXTRA_INCLUDES) $($<.INCLUDES) $($@.INCLUDES)
compilecxxflags = $(CXXFLAGS) $(EXTRA_FLAGS) $($<.FLAGS) $($@.FLAGS) -MQ $@ -MMD -MF $@.d
%.o: %.cc
	$(QECHO) CXX $@
	$Q $(CCACHE) $(CXX) $(CXXSTD) $(compiledefs) $(compilecxxflags) -o $@ -c $<
CLEANFILES += cxx/*.o cxx/*.o.d cxx/*.map

# == cxx/imagewmark (add only) ==
cxx/imagewmark.sources := cxx/imagewmark-add.cc cxx/utils.cc cxx/random.cc cxx/convcode.cc cxx/embed.cc
cxx/imagewmark.objects := $(cxx/imagewmark.sources:.cc=.o)
cxx/imagewmark.LIBS    := $(cxx/libvips.libs)
$(cxx/imagewmark.objects): $(CXXDEPS)
cxx/embed.cc.FLAGS     := $(cxx/libvips.cflags)
cxx/imagewmark: $(cxx/imagewmark.objects)
	$(QGEN)
	$Q $(LINK) $(cxx/imagewmark.objects) $(LDLIBS) $($@.LIBS) -o $@ -Wl,--print-map >$@.map
ALL_TARGETS += cxx/imagewmark

# == cxx/wmops (get and helpers) ==
cxx/wmops.sources := cxx/wmops.cc cxx/utils.cc cxx/random.cc cxx/convcode.cc
cxx/wmops.objects := $(cxx/wmops.sources:.cc=.o)
cxx/wmops.LIBS    := $(cxx/opencv4.libs)
$(cxx/wmops.objects): $(CXXDEPS)
cxx/wmops: $(cxx/wmops.objects)
	$(QGEN)
	$Q $(LINK) $(cxx/wmops.objects) $(LDLIBS) $($@.LIBS) -o $@ -Wl,--print-map >$@.map
ALL_TARGETS += cxx/wmops

# == cxx/peaks2grid ==
cxx/peaks2grid.sources := cxx/peaks2grid.cc
cxx/peaks2grid.objects := $(cxx/peaks2grid.sources:.cc=.o)
cxx/peaks2grid: $(cxx/peaks2grid.objects)
	$(QGEN)
	$Q $(LINK) $(cxx/peaks2grid.objects) $(LDLIBS) $($@.LIBS) -o $@ -Wl,--print-map >$@.map
ALL_TARGETS += cxx/peaks2grid

# == cxx/cornersync ==
cxx/cornersync.sources := cxx/cornersync.cc
cxx/cornersync.objects := $(cxx/cornersync.sources:.cc=.o)
cxx/cornersync.cc.FLAGS := $(cxx/opencv4.cflags)
cxx/cornersync.LIBS     := $(cxx/opencv4.libs)
cxx/cornersync: $(cxx/cornersync.objects)
	$(QGEN)
	$Q $(LINK) $(cxx/cornersync.objects) $(LDLIBS) $($@.LIBS) -o $@ -Wl,--print-map >$@.map
ALL_TARGETS += cxx/cornersync

# == Tests ==
cxx/test-convcode-check: cxx/wmops
	$(QCHECK)
	$Q cxx/wmops convcode-check
	$(QOK)
cxx/check: cxx/test-convcode-check
.PHONY: cxx/check cxx/test-convcode-check cxx/test-imagewmark-add
check: cxx/check

# == test add --py ==
cxx/check-add--py-768: .version imagewmark cxx/peaks2grid cxx/cornersync
	$Q echo '  CHECK   ' $@
	$Q convert tests/example01.svg -resize 768 $@.png
	$Q ./cxx/imagewmark add --py $@.png $@.wm.png $(src/watermark)
	$Q ./imagewmark get $@.wm.png --json $@.json
	$Q grep -qE '\b$(src/watermark)\b' $@.json || \
		{ echo "$@.png: failed to detect watermark" >&2 ; false ; }
	$Q rm $@.png $@.wm.png $@.json
	$Q echo '  OK      ' $@
.PHONY: cxx/check-add--py-768

# == test add --cxx ==
cxx/check-add--cxx-768: .version imagewmark cxx/peaks2grid cxx/cornersync
	$Q echo '  CHECK   ' $@
	$Q convert tests/example01.svg -resize 768 $@.png
	$Q ./cxx/imagewmark add $@.png $@.wm.png $(src/watermark)
	$Q ./imagewmark get $@.wm.png --json $@.json
	$Q grep -qE '\b$(src/watermark)\b' $@.json || \
		{ echo "$@.png: failed to detect watermark" >&2 ; false ; }
	$Q rm $@.png $@.wm.png $@.json
	$Q echo '  OK      ' $@
.PHONY: cxx/check-add--cxx-768
cxx/check: cxx/check-add--py-768 cxx/check-add--cxx-768
