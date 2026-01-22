# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

# == pandoc for manual pages ==
doc/markdown-flavour := markdown-hard_line_breaks+pandoc_title_block+autolink_bare_uris+emoji+lists_without_preceding_blankline
doc/mans1            :=

# == doc/imagewmark-arch--help.md Helper ==
doc/imagewmark-arch--help.md: doc/imagewmark-arch.md src/imagewmark.py doc/Makefile.mk
	$Q sed -e '/@:sed:usage_imagewmark-h:@/e src/imagewmark.py -h' -e '/@:sed:[a-zA-Z0-9_+-]*:@/d' $< > $@
CLEANFILES += doc/imagewmark-arch--help.md

# == doc/imagewmark-arch.html ==
doc/imagewmark-arch.html: doc/imagewmark-arch--help.md
	$(QGEN)
	$Q pandoc $< -o $@
ALL_TARGETS += doc/imagewmark-arch.html

# == doc/imagewmark-arch.pdf ==
HAVE_PDFLATEX != command -V pdflatex 2>/dev/null && echo pdflatex
ifeq ($(HAVE_PDFLATEX),pdflatex)
doc/imagewmark-arch.pdf: doc/imagewmark-arch--help.md
	$(QGEN)
	$Q pandoc -V papersize:a4 -V geometry:margin=2cm $< -o $@
ALL_TARGETS += doc/imagewmark-arch.pdf
endif

# == imagewmark.1 ==
doc/imagewmark.1: doc/imagewmark.1.md doc/Makefile.mk
	$(QGEN)
	$Q SECONDS="$$(git log -1 --format=%ct -- $< 2>/dev/null || stat -c %Y $<)" \
	&& $(PANDOC) -p -f $(doc/markdown-flavour) \
		-M date="$$(date +%Y-%m-%d -d "@$$SECONDS")" \
		-M footer="imagewmark-$(VERSION)" \
		-t man -s -o $@.tmp $<
	$Q mv $@.tmp $@
doc/mans1 += doc/imagewmark.1

# == targets ==
ALL_TARGETS += $(doc/mans1)
