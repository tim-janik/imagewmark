# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
# Makefile for imagewmark test runs

all:
SHELL		:= /bin/bash
.SHELLFLAGS	:= -Eeuo pipefail -c
MAKEFILE	:= $(lastword $(MAKEFILE_LIST))
Q		:= $(if $(findstring 1, $(V)),, @)
QGEN		 = @echo '  GEN     ' $@
QECHO		 = @QECHO() { Q1="$$1"; shift; QR="$$*"; QOUT=$$(printf '  %-8s ' "$$Q1" ; echo "$$QR") && echo "$$QOUT"; }; QECHO
SRCDIR		?= $(dir $(MAKEFILE))/..
WATERMARK	?= fedcba98765432100123456789abcdef
ATTACK_IMAGES	:=
RESULT_REPORTS	:=
__TESTKEY       := $(if $(TESTKEY), --test-key $(TESTKEY) )

MAGICK_CONFIGURE_PATH != pwd
export MAGICK_CONFIGURE_PATH

IMAGEDIR	?= ../input
#IMAGEDIR	:= $(abspath $(IMAGEDIR))
ABS_INPUT_IMAGES := $(wildcard $(IMAGEDIR)/*.* $(IMAGEDIR)/*/*.* $(IMAGEDIR)/*/*/*.* $(IMAGEDIR)/*/*/*/*.*)
REL_INPUT_IMAGES := $(ABS_INPUT_IMAGES:$(IMAGEDIR)/%=%)

# == help ==
help:
	@echo 'Make targets:'
	@echo '  all			- Collect input images, create attack images, extract watermarks'
	@echo '  attacks		- Collect input images, create attack images'
	@echo '  clean			- Remove all images and reports'
	@echo 'Invocation:'
	@echo '  make V=1		- Enable verbose output from MAKE and subcommands'
	@echo '  make IMAGEDIR=..	- Specifc directory with images for testing'

# == check-nproc ==
check-nproc:
	@ JJ=`echo ' $(MAKEFLAGS) ' | sed -nr '/ -j| --jobs\b/{ s/--jobserver[^ ]*//; s/.* (-j|--jobs=?) *([0-9]*).*/\2/; s/^$$/999999/; p; q; }' ` \
	&& test "$${JJ:-0}" -le `nproc` || { echo "$(MAKEFILE): too many make jobs (max supported: `nproc`)" ; false ; }
# refuse parallel make with more jobs than nproc, this is very likely to run into the OOM killer
$(MAKEFILE): check-nproc
.PHONY: check-nproc

# == inputs/ ==
INPUTS :=
define INPUTS_STEM_LINK
INPUTS += inputs/$$(basename $1)
inputs/$$(basename $1): $(1:%=$$(IMAGEDIR)/%)
	$$(QECHO) LNK $$@
	$Q mkdir -p $$(dir $$@)
	$Q test -L $$@ || ln -sv $$(abspath $$<) $$@
endef
$(foreach I, $(REL_INPUT_IMAGES), $(eval $(call INPUTS_STEM_LINK, $I)))
.NOTINTERMEDIATE: $(INPUTS)

# == wmarked/ ==
WMARKED_IMAGES := $(INPUTS:inputs/%=wmarked/%)
wmarked/%: inputs/%
	$(QECHO) ADD $@
	$Q mkdir -p $(dir $@)
	$Q $(SRCDIR)/imagewmark add $(__TESTKEY) $< $@.png $(WATERMARK)
	$Q mv $@.png $@
.NOTINTERMEDIATE: $(WMARKED_IMAGES)

# == attack/ ==
# jpeg	  	echo "jpeg:90 jpeg:70 jpeg:50 jpeg:30"
# rotation	  echo "rotate:5:15|jpeg:90 rotate:0:180|jpeg:90"
# cropping	  echo "crop:25:25|jpeg:90 crop:50:50|jpeg:90 crop:75:75|jpeg:90 crop:90:90|jpeg:90"
# upscaling + jpeg	  echo "crop:75:95|scale:100:200|jpeg:90"
ATTACKS := jpg30 jpg50 jpg70 jpg90 noise noisej90 noisej90 rot5to15j90 rot0to180j90 crop75j90 crop50scale200j90 noisecrop50scale200j90 noise2crop50scale200j90 \
	   j90cropscaleto512j90seed1 j90cropscaleto512j70seed1 \
	   j90cropscaleto512j90seed2 j90cropscaleto512j70seed2 \
	   j90cropscaleto512j90seed3 j90cropscaleto512j70seed3 \
	   j90scaleto512j90 j90scaleto512j70 \
	   j90scaleto768j90 j90scaleto768j70 j90scaleto768j50
jpg30			= convert $<			-quality 30		$@.jpg && mv $@.jpg $@
jpg50			= convert $<			-quality 50		$@.jpg && mv $@.jpg $@
jpg70			= convert $<			-quality 70		$@.jpg && mv $@.jpg $@
jpg90			= convert $<			-quality 90		$@.jpg && mv $@.jpg $@
noise			= convert $<	-seed 123 +noise Gaussian		$@.png && mv $@.png $@
noisej90		= convert $<	-seed 123 +noise Gaussian -quality 90	$@.jpg && mv $@.jpg $@
rot5to15j90		= $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<) --attack "rotate:5:15|jpeg:90" $@.png && mv $@.png $@
rot0to180j90		= $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<) --attack "rotate:0:180|jpeg:90" $@.png && mv $@.png $@
crop75j90		= convert $< -gravity Center -crop 75x75%+0+0 -quality 90	$@.jpg && mv $@.jpg $@
crop50scale200j90	= convert $< -gravity Center -crop 50x50%+0+0 -resize 200% -quality 90	$@.jpg && mv $@.jpg $@
noisecrop50scale200j90	= convert $< -seed 123 +noise Gaussian -gravity Center -crop 50x50%+0+0 -resize 200% 		   -quality 90	$@.jpg && mv $@.jpg $@
noise2crop50scale200j90	= convert $< -seed 123 +noise Gaussian -gravity Center -crop 50x50%+0+0 -resize 200% -seed 456 +noise Gaussian -quality 90	$@.jpg && mv $@.jpg $@
j90cropscaleto512j90seed1 = $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):1 --attack "jpeg:90|crop:50:95|scaleto:512|jpeg:90" $@.png && mv $@.png $@
j90cropscaleto512j90seed2 = $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):2 --attack "jpeg:90|crop:50:95|scaleto:512|jpeg:90" $@.png && mv $@.png $@
j90cropscaleto512j90seed3 = $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):3 --attack "jpeg:90|crop:50:95|scaleto:512|jpeg:90" $@.png && mv $@.png $@
j90cropscaleto512j70seed1 = $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):1 --attack "jpeg:90|crop:50:95|scaleto:512|jpeg:70" $@.png && mv $@.png $@
j90cropscaleto512j70seed2 = $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):2 --attack "jpeg:90|crop:50:95|scaleto:512|jpeg:70" $@.png && mv $@.png $@
j90cropscaleto512j70seed3 = $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):3 --attack "jpeg:90|crop:50:95|scaleto:512|jpeg:70" $@.png && mv $@.png $@
j90scaleto512j90	= $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):3 --attack "jpeg:90|scaleto:512|jpeg:90" $@.png && mv $@.png $@
j90scaleto512j70	= $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):3 --attack "jpeg:90|scaleto:512|jpeg:70" $@.png && mv $@.png $@
j90scaleto768j90	= $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):3 --attack "jpeg:90|scaleto:768|jpeg:90" $@.png && mv $@.png $@
j90scaleto768j70	= $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):3 --attack "jpeg:90|scaleto:768|jpeg:70" $@.png && mv $@.png $@
j90scaleto768j50	= $(SRCDIR)/tests/wmtool.py $< --seed $(shell basename $<):3 --attack "jpeg:90|scaleto:768|jpeg:50" $@.png && mv $@.png $@
define ATTACK_RULE
$(1:%=attack/%)/%: wmarked/%
	$$(QECHO) $1 $$@
	$Q mkdir -p $$(dir $$@)
	$Q $$(call $(1), $$<, $$@)
ATTACK_IMAGES += $$(WMARKED_IMAGES:wmarked/%=$(1:%=attack/%)/%)
endef
$(foreach A, $(ATTACKS), $(eval $(call ATTACK_RULE, $(A))))
.NOTINTERMEDIATE: $(ATTACK_IMAGES)

# == attacks ==
attacks: $(ATTACK_IMAGES)
.PHONY: attacks

# == extract ==
EXTRACT_FILES := $(ATTACK_IMAGES:attack/%=extract/%.json)
extract/%.json: attack/%
	$(QECHO) GET $@
	$Q mkdir -p $(dir $@)
	$Q $(SRCDIR)/imagewmark get $(__TESTKEY) --expect $(WATERMARK) $< --json > $@.tmp
	$Q grep -qw "$(WATERMARK)" $@.tmp || { \
	  echo '  ALIGNED  ' $@ \
	&& $(SRCDIR)/imagewmark get $(__TESTKEY) --expect $(WATERMARK) $< --json \
				--original inputs/$(notdir $(<:%.json=%))	 > $@.tmp ; }
	$Q mv $@.tmp $@
.NOTINTERMEDIATE: $(EXTRACT_FILES)

# == pandoc rules ==
REPORT_FORMAT := markdown+compact_definition_lists+autolink_bare_uris+emoji+lists_without_preceding_blankline-smart-raw_tex-raw_html
%.html: %.md $(MAKEFILE)
	$(QGEN)
	$Q pandoc -f "$(REPORT_FORMAT)" $< -o $@.tmp.html
	$Q mv $@.tmp.html $@
%.pdf: %.md $(MAKEFILE)
	$(QGEN)
	$Q pandoc -f "$(REPORT_FORMAT)" $< -o $@.tmp.pdf
	$Q mv $@.tmp.pdf $@

# == reports ==
report.md: $(EXTRACT_FILES) $(MAKEFILE) $(SRCDIR)/tests/report.py
	$(QGEN)
	$Q $(SRCDIR)/tests/report.py $(WATERMARK) >$@.tmp
	$Q mv $@.tmp $@
RESULT_REPORTS += report.html report.pdf
flat.txt: $(EXTRACT_FILES) $(MAKEFILE) $(SRCDIR)/tests/report.py
	$(QGEN)
	$Q $(SRCDIR)/tests/report.py --flat $(WATERMARK) >> $@.tmp
	$Q mv $@.tmp $@
RESULT_REPORTS += flat.txt
fails.txt: flat.txt
	$(QGEN)
	$Q fgrep -v ' OK' flat.txt > $@.tmp || :
	$Q mv $@.tmp $@
RESULT_REPORTS += fails.txt
all: $(RESULT_REPORTS)
	$(QGEN)
	$Q echo "IMAGEDIR:        " $(IMAGEDIR)
	$Q echo "REL_INPUT_IMAGES:" $(words $(REL_INPUT_IMAGES))
	$Q echo "WMARKED_IMAGES:  " $(words $(WMARKED_IMAGES))
	$Q echo "ATTACK_IMAGES:   " $(words $(ATTACK_IMAGES))
	$Q echo "EXTRACT_FILES:   " $(words $(EXTRACT_FILES))
	$Q echo "EXTRACT_FILES:   " $(words $(EXTRACT_FILES))
	$Q ls -l $(RESULT_REPORTS)

# == test ==
test: all
.PHONY: test

# == clean ==
clean-attack:
	rm -rf ../tests/attack/
clean-extract:
	rm -rf ../tests/extract/ ../tests/aligned/
clean-reports:
	rm -f *.tmp *.svg $(RESULT_REPORTS) report.md
clean: clean-attack clean-extract clean-reports
	rm -rf ../tests/wmarked/ ../tests/inputs/

# TODO: json: prefix imagewmark get results with image file name
# TODO: json: add filename field
# TODO: json: add single 'watermark' and 'confidence' field
# TODO: add timings, PSNR
