# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
# Makefile for imagewmark test runs

all:
SHELL		:= /bin/bash
.SHELLFLAGS	:= -Eeuo pipefail -c
MAKEFILE	:= $(lastword $(MAKEFILE_LIST))
Q		:= $(if $(findstring 1, $(V)),, @)
QGEN		 = @echo '  GEN     ' $@
QECHO		 = @QECHO() { Q1="$$1"; shift; QR="$$*"; QOUT=$$(printf '  %-8s ' "$$Q1" ; echo "$$QR") && echo "$$QOUT"; }; QECHO
ATTACK_IMAGES	:=
RESULT_REPORTS	:=
__TESTKEY       := $(if $(TESTKEY), --test-key $(TESTKEY) )
SRCDIR			?= $(dir $(MAKEFILE))/..
IMAGEWMARK		?= $(SRCDIR)/imagewmark
WATERMARK		?= fedcba98765432100123456789abcdef
SEED			?= 0
WITHOUT_ORIGINAL	?= false
CORNERSYNC_MODE		?= auto

MAGICK_CONFIGURE_PATH != pwd
export MAGICK_CONFIGURE_PATH

# == help ==
help:
	@echo 'Make targets:'
	@echo '  all			- Collect input images, create attack images, extract watermarks'
	@echo '  attacks		- Collect input images, create attack images'
	@echo '  clean			- Remove all images and reports'
	@echo 'Invocation:'
	@echo '  make V=1		- Enable verbose output from MAKE and subcommands'
	@echo '  make IMAGEDIR=..	- Specifc directory with images for testing'
	@echo '  make SEED=<integer>	- Alter seed for randomized tests'

# == check-nproc ==
check-nproc:
	@ JJ=`echo ' $(MAKEFLAGS) ' | sed -nr '/ -j| --jobs\b/{ s/--jobserver[^ ]*//; s/.* (-j|--jobs=?) *([0-9]*).*/\2/; s/^$$/999999/; p; q; }' ` \
	&& test "$${JJ:-0}" -le `nproc` || { echo "$(MAKEFILE): too many make jobs (max supported: `nproc`)" ; false ; }
# refuse parallel make with more jobs than nproc, this is very likely to run into the OOM killer
$(MAKEFILE): check-nproc
.PHONY: check-nproc

# == inputs/ ==
IMAGEDIR ?=
ifeq ($(strip $(IMAGEDIR)),)
INPUTS := $(wildcard inputs/*)
else
INPUTS :=
IMAGEDIR_GLOB := $(wildcard $(IMAGEDIR)/*.* $(IMAGEDIR)/*/*.* $(IMAGEDIR)/*/*/*.* $(IMAGEDIR)/*/*/*/*.*)
define INPUTS_STEM_LINK
INPUTS += inputs/$$(basename $1)
inputs/$$(basename $1): $(1:%=$$(IMAGEDIR)/%)
	$$(QECHO) LNK $$@
	$Q mkdir -p $$(dir $$@)
	$Q test -L $$@ || ln -sv $$(abspath $$<) $$@
endef
$(foreach I, $(IMAGEDIR_GLOB), $(eval $(call INPUTS_STEM_LINK, $I)))
.NOTINTERMEDIATE: $(INPUTS)
endif

# == wmarked/ ==
WMARKED_IMAGES := $(INPUTS:inputs/%=wmarked/%)
wmarked/%: inputs/%
	$(QECHO) ADD $@
	$Q mkdir -p $(dir $@)
	$Q $(IMAGEWMARK) add $(__TESTKEY) $< $@.png $(WATERMARK)
	$Q mv $@.png $@
.NOTINTERMEDIATE: $(WMARKED_IMAGES)

# == attack/ ==
# jpeg			echo "jpeg:90 jpeg:70 jpeg:50 jpeg:30"
# rotation		echo "rotate:5:15|jpeg:90 rotate:0:180|jpeg:90"
# cropping		echo "crop:25:25|jpeg:90 crop:50:50|jpeg:90 crop:75:75|jpeg:90 crop:90:90|jpeg:90"
# upscaling + jpeg	echo "crop:75:95|scale:100:200|jpeg:90"
DEFAULT_ATTACKS  :=
EXTENDED_ATTACKS :=

# DEFAULT
jpg70                  = convert $<			-quality 70		-strip $@.jpg && mv $@.jpg $@
DEFAULT_ATTACKS       += jpg70
jpg90                  = convert $<			-quality 90		-strip $@.jpg && mv $@.jpg $@
DEFAULT_ATTACKS       += jpg90
noisej90               = convert $<	-seed $1 +noise Gaussian -quality 90	-strip $@.jpg && mv $@.jpg $@
DEFAULT_ATTACKS       += noisej90
j90scaleto512j80       = $(SRCDIR)/tests/wmtool.py --seed $1 --attack "jpeg:90|scaleto:512|jpeg:80" $< $@.png && mv $@.png $@
DEFAULT_ATTACKS       += j90scaleto512j80
j90randomsizej80g = $(SRCDIR)/tests/wmtool.py --seed $1 --attack "jpeg:90|aspect-resize:$(RANDOMSIZE)|jpeg:80" $< $@.png && mv $@.png $@
DEFAULT_ATTACKS       += j90randomsizej80g
brightnesscontrast10j90 = convert $<	-seed $1 -brightness-contrast 10x10 -quality 90	-strip $@.jpg && mv $@.jpg $@
DEFAULT_ATTACKS        += brightnesscontrast10j90
gamma05j90              = convert $<	-seed $1 -gamma 0.5		   -quality 90	-strip $@.jpg && mv $@.jpg $@
DEFAULT_ATTACKS        += gamma05j90
# geometrical attacks
rot0to180j90g		= $(SRCDIR)/tests/wmtool.py --seed $1 --attack "rotate:0:180|jpeg:90" $< $@.png && mv $@.png $@
DEFAULT_ATTACKS        += rot0to180j90g
j90crop50scaleto512j80g = $(SRCDIR)/tests/wmtool.py --seed $1 --attack "jpeg:90|crop:50:50|scaleto:512|jpeg:80" $< $@.png && mv $@.png $@
DEFAULT_ATTACKS        += j90crop50scaleto512j80g

# EXTENDED
jpg30                  = convert $<			-quality 30		-strip $@.jpg && mv $@.jpg $@
EXTENDED_ATTACKS      += jpg30
jpg50                  = convert $<			-quality 50		-strip $@.jpg && mv $@.jpg $@
EXTENDED_ATTACKS      += jpg50
noise                  = convert $<	-seed $1 +noise Gaussian		-strip $@.png && mv $@.png $@
EXTENDED_ATTACKS      += noise
j90scaleto512j90       = $(SRCDIR)/tests/wmtool.py --seed $1 --attack "jpeg:90|scaleto:512|jpeg:90" $< $@.png && mv $@.png $@
EXTENDED_ATTACKS      += j90scaleto512j90
j90scaleto768j90       = $(SRCDIR)/tests/wmtool.py --seed $1 --attack "jpeg:90|scaleto:768|jpeg:90" $< $@.png && mv $@.png $@
EXTENDED_ATTACKS      += j90scaleto768j90
j90scaleto768j70       = $(SRCDIR)/tests/wmtool.py --seed $1 --attack "jpeg:90|scaleto:768|jpeg:70" $< $@.png && mv $@.png $@
EXTENDED_ATTACKS      += j90scaleto768j70
j90scaleto768j50       = $(SRCDIR)/tests/wmtool.py --seed $1 --attack "jpeg:90|scaleto:768|jpeg:50" $< $@.png && mv $@.png $@
EXTENDED_ATTACKS      += j90scaleto768j50
# centered cropping (well detected by corner sync)
centered75j90          = convert $< -gravity Center -crop 75x75%+0+0 -quality 90	-strip $@.jpg && mv $@.jpg $@
EXTENDED_ATTACKS      += centered75j90
centered50scale200j90  = convert $< -gravity Center -crop 50x50%+0+0 -resize 200% -quality 90	-strip $@.jpg && mv $@.jpg $@
EXTENDED_ATTACKS      += centered50scale200j90
noisecentered50scale200j90   = convert $< -seed $1 +noise Gaussian -gravity Center -crop 50x50%+0+0 -resize 200% 		   -quality 90	-strip $@.jpg && mv $@.jpg $@
EXTENDED_ATTACKS      += noisecentered50scale200j90
noise2centered50scale200j90  = convert $< -seed $1 +noise Gaussian -gravity Center -crop 50x50%+0+0 -resize 200% +noise Gaussian -quality 90	-strip $@.jpg && mv $@.jpg $@
EXTENDED_ATTACKS      += noise2centered50scale200j90
# geometrical attacks
rot5to15j90g            = $(SRCDIR)/tests/wmtool.py --seed $1 --attack "rotate:5:15|jpeg:90" $< $@.png && mv $@.png $@
EXTENDED_ATTACKS       += rot5to15j90g
j90crop60scaleto512j70g = $(SRCDIR)/tests/wmtool.py --seed $1 --attack "jpeg:90|crop:60:60|scaleto:512|jpeg:70" $< $@.png && mv $@.png $@
EXTENDED_ATTACKS       += j90crop60scaleto512j70g

ATTACKS			?= $(DEFAULT_ATTACKS)

ifeq ($(CORNERSYNC_MODE),on)
EXTENDED_ATTACKS := $(filter-out %g, $(EXTENDED_ATTACKS))
DEFAULT_ATTACKS := $(filter-out %g, $(DEFAULT_ATTACKS))
endif

info:
	@echo EXTENDED_ATTACKS=$(EXTENDED_ATTACKS)
	@echo DEFAULT_ATTACKS=$(DEFAULT_ATTACKS)

define ATTACK_RULE
$(1:%=attack/%)/%: wmarked/%
	$$(QECHO) $1 $$@
	$Q mkdir -p $$(dir $$@)
	$Q $$(call $(1), $$(SEED))
ATTACK_IMAGES += $$(WMARKED_IMAGES:wmarked/%=$(1:%=attack/%)/%)
endef
$(foreach A, $(ATTACKS), $(eval $(call ATTACK_RULE, $(A))))
.NOTINTERMEDIATE: $(ATTACK_IMAGES)

# == Random Size Configuration ==
ATTACK_RANDOMSIZE := attack/j90randomsizej80g
-include randomsize.inc

# == attacks ==
attacks: $(ATTACK_IMAGES)
.PHONY: attacks

# == extract ==
EXTRACT_FILES := $(ATTACK_IMAGES:attack/%=extract/%.json)
extract/%.json: attack/%
	$(QECHO) GET $@
	$Q mkdir -p $(dir $@)
	$Q $(IMAGEWMARK) get $(__TESTKEY) --expect $(WATERMARK) --cornersync $(CORNERSYNC_MODE) $< --json > $@.tmp
	$Q $(WITHOUT_ORIGINAL) || grep -qw "$(WATERMARK)" $@.tmp || { \
	  echo '  ALIGNED  ' $@ \
	&& $(IMAGEWMARK) get $(__TESTKEY) --expect $(WATERMARK) $< --json \
				--original inputs/$(notdir $(<:%.json=%))	 > $@.tmp ; }
	$Q mv $@.tmp $@
.NOTINTERMEDIATE: $(EXTRACT_FILES)

# == pandoc rules ==
REPORT_FORMAT := markdown+autolink_bare_uris+emoji+lists_without_preceding_blankline-smart-raw_tex-raw_html
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
RESULT_REPORTS += report.md report.html report.pdf
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
	$(file > EXTRACT_FILES.lst, $(EXTRACT_FILES))
	$(QGEN)
	$Q echo "IMAGEDIR:        " $(IMAGEDIR)
	$Q echo "WMARKED_IMAGES:  " $(words $(WMARKED_IMAGES))
	$Q echo "SEED:            " $(SEED)
	$Q echo "ATTACK_IMAGES:   " $(words $(ATTACK_IMAGES))
	$Q echo "EXTRACT_FILES:   " $(words $(EXTRACT_FILES))
	$Q echo "MATCHING:        " $$(xargs -aEXTRACT_FILES.lst grep -w "$(WATERMARK)" | wc -l)
	$Q rm -f EXTRACT_FILES.lst
	$Q ls -l $(abspath $(RESULT_REPORTS))

# == test ==
test: all
.PHONY: test

# == clean ==
clean-attack:
	rm -rf ../tests/attack/
clean-extract:
	rm -rf ../tests/extract/
clean-reports:
	rm -f *.tmp *.svg $(RESULT_REPORTS) report.md
clean: clean-attack clean-extract clean-reports
	rm -rf ../tests/wmarked/ ../tests/inputs/
