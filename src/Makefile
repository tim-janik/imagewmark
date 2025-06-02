# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
all:

CXXFLAGS	:= -O2 -Wall -g -std=c++17
WATERMARK       := fedcba98765432100123456789abcdef
Q		:= $(if $(findstring 1, $(V)),, @)

all: peaks2grid cornersync

peaks2grid: peaks2grid.cc minsearch.hh
	$(CXX) $(CXXFLAGS) -o peaks2grid peaks2grid.cc $(shell ./opencv-check.sh)

cornersync: cornersync.cc
	$(CXX) $(CXXFLAGS) -o cornersync cornersync.cc $(shell ./opencv-check.sh)

clean:
	rm -f peaks2grid convcode cornersync

# == check ==
check:
.PHONY: check
define CHECK_RESOLUTION
check-$1:
	$(Q) echo '  CHECK   ' $$@
	$(Q) convert ../tests/example01.svg -resize $1 $$@.png
	$(Q) ./imagewmark add $$@.png $$@.wm.png $(WATERMARK)
	$(Q) ./imagewmark get $$@.wm.png --json $$@.json
	$(Q) grep -qE '\b$(WATERMARK)\b' $$@.json || \
		{ echo "$$@.png: failed to detect watermark" >&2 ; false ; }
	$(Q) rm $$@.png $$@.wm.png $$@.json
	$(Q) echo '  OK      ' $$@
.PHONY: check-$1
check: check-$1
endef
CHECK_RESOLUTIONS := 1024 2048 3072 4096 # 8192
$(foreach R, $(CHECK_RESOLUTIONS), $(eval $(call CHECK_RESOLUTION,$R)))
