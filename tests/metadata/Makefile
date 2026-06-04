# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
all:	# default target

MAKEFLAGS	+= --no-builtin-rules
Q		:= $(if $(findstring 1, $(V)),, @)
QGEN		 = @echo '  GEN     ' $@
TTY		!= test ! -t 1 || echo 1
IMAGEWMARK	:= ../../imagewmark
IMAGEWMARK_ADD	:= $(IMAGEWMARK) add
EXTRACT_META	:= ../../tests/metadata/extract-metadata.sh
FILTER_META	:= ../../tests/metadata/filter-metadata.sh
WATERMARK	:= 00001234
MAKEFILE_DEP	:= Makefile


# Recursively find globs and list shell-quoted file names
globstar = $(shell /bin/bash --norc -O globstar -O nullglob -c 'files=($(1:%=**/%)); test $${#files[@]} -le 0 || printf "%q\n" "$${files[@]}"')

## Fetch the exif-samples image set via git clone, plus PNG/WebP/GIF from metadata-extractor-images
examples:
	rm -rf exif-samples/ alt-examples/
	git clone --depth 1 https://github.com/ianare/exif-samples.git
	rm -f exif-samples/jpg/corrupted.jpg
	mv exif-samples/jpg/WWL_\(Polaroid\)_ION230.jpg exif-samples/jpg/WWL_.Polaroid._ION230.jpg
	mkdir -p alt-examples/
	curl -sLo alt-examples/sampleWithExifData.png 'https://github.com/drewnoakes/metadata-extractor-images/raw/main/png/sampleWithExifData.png'
	curl -sLo alt-examples/Nikon_D1X.webp 'https://github.com/drewnoakes/metadata-extractor-images/raw/main/webp/Nikon%20D1X.webp'
	curl -sLo alt-examples/Issue_201.gif 'https://github.com/drewnoakes/metadata-extractor-images/raw/main/gif/Issue%20201.gif'
	curl -sLo alt-examples/Issue_649.avif 'https://github.com/drewnoakes/metadata-extractor-images/raw/main/avif/Issue%20649.avif'

# Collect image files of interest, except .wm. files - we create those
IMAGE_FILES := $(call globstar, *.jpeg *.jpg *.tiff *.png *.webp *.gif *.avif) # *.heif *.HEIC
IMAGE_FILES := $(foreach f,$(IMAGE_FILES),$(if $(findstring .wm.,$(f)),,$(f)))
## List all input images
ls:
	$Q printf '%s\n' $(IMAGE_FILES)
## Verify test images are present
input_check:
	$Q test -z "$(strip $(IMAGE_FILES))" || exit 0 ; \
	   echo "$@: Failed to find input images, to populate run: make examples" >&2 ; false

# Transform path/image.ext -> path/image.wm.ext
add.wm = $(basename $1).wm$(suffix $1)
ls.wm: ; printf '%s\n' $(WM_FILES)
WM_FILES = $(foreach img,$(IMAGE_FILES),$(call add.wm,$(img)))

# Targets have different suffixes, so we must generate rules:
# img.wm.ext: img.ext ; imagewmark add $< $@ <watermark>
$(foreach img,$(IMAGE_FILES),$(eval \
  $(call add.wm,$(img)) : $(img) ; $(QGEN) $$@ && $(IMAGEWMARK_ADD) $$< $$@ $(WATERMARK) \
))
$(WM_FILES) : $(IMAGEWMARK) $(MAKEFILE_DEP)

# Transform path/file -> path/file.mdata
MDATA_FILES := $(IMAGE_FILES:%=%.mdata) $(WM_FILES:%=%.mdata)
# Generate .mdata files with extracted metadata
%.mdata: %
	$(QGEN)
	$Q $(EXTRACT_META) $< > $@.tmp && mv $@.tmp $@
$(MDATA_FILES) : $(EXTRACT_META) $(MAKEFILE_DEP)

# Transform path/file.mdata -> path/file.fdata (filtered metadata)
FDATA_FILES := $(IMAGE_FILES:%=%.fdata) $(WM_FILES:%=%.fdata)
%.fdata: %.mdata
	$(QGEN)
	$Q $(FILTER_META) $< > $@.tmp && mv $@.tmp $@
$(FDATA_FILES) : $(FILTER_META) $(MAKEFILE_DEP)

# Transform path/image.ext -> path/image.ext.mdiff - show metadata differences
MDIFF_FILES := $(IMAGE_FILES:%=%.mdiff)
ls.mdiff: ; printf '%s\n' $(MDIFF_FILES)
# image.ext.mdiff: img.ext.fdata img.wm.ext.fdata
$(foreach I,$(IMAGE_FILES),$(eval \
  $I.mdiff : $(call add.wm,$I).fdata $I.fdata $(MAKEFILE_DEP) ; $(QGEN) $$@ && diff -U0 $I.fdata $$< > $$@.tmp ; mv $$@.tmp $$@ \
))

GENERATED_FILES = $(WM_FILES) $(MDATA_FILES) $(MDIFF_FILES)
## Remove generated files: .wm .mdata .mdiff
## as well as temporary files
clean: clean-tmp
	rm -f $(GENERATED_FILES)
clean-tmp:
	rm -f $(GENERATED_FILES:=.tmp)

## show this help
help:
	$Q TTY=1; test -t 1 || TTY=; \
	   awk -v tty="$$TTY" \
		'BEGIN { ci=tty?"\033[36m":""; cr=tty?"\033[0m":"" } \
		/^## / { c = c (c ? "\n             " : "") substr($$0, 4); next; } \
		{ if (/^[a-zA-Z_-]+:/ && c) { split($$1,t,/:/); printf "%s%-12s%s %s\n",ci,t[1],cr,c; }; c=""; }' \
		$(MAKEFILE_LIST)


## Default target
all: input_check $(MDIFF_FILES)
