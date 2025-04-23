# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

doc/mans :=

# == pandoc ==
doc/markdown-flavour   = markdown-hard_line_breaks+compact_definition_lists+pandoc_title_block+autolink_bare_uris+emoji+lists_without_preceding_blankline

# == imagewmark-arch ==
doc/imagewmark-arch--help.md: doc/imagewmark-arch.md doc/Makefile.mk
	$Q sed -e '/@:sed:usage_imagewmark-h:@/e ./src/imagewmark -h' -e '/@:sed:[a-zA-Z0-9_+-]*:@/d' $< > $@.tmp
	$Q mv $@.tmp $@

doc/imagewmark-arch.html: doc/imagewmark-arch--help.md
	$Q pandoc $< -o $@
ALL_TARGETS += doc/imagewmark-arch.html
CLEANFILES  += doc/imagewmark-arch.html

doc/imagewmark-arch.pdf: doc/imagewmark-arch--help.md
	$Q pandoc -V papersize:a4 -V geometry:margin=2cm $< -o $@
ALL_TARGETS += doc/imagewmark-arch.pdf
CLEANFILES  += doc/imagewmark-arch.pdf

# == imagewmark.1 ==
doc/imagewmark.1: doc/imagewmark.1.md Makefile doc/Makefile.mk
	$Q SECONDS="$$(git log -1 --format=%ct -- $< 2>/dev/null || stat -c %Y $<)" \
	&& $(PANDOC) -p -f $(doc/markdown-flavour) \
		-M date="$$(date +%Y-%m-%d -d "@$$SECONDS")" \
		-M footer="imagewmark-$(VERSION)" \
		-t man -s -o $@.tmp $<
	$Q mv $@.tmp $@
doc/mans += doc/imagewmark.1

# == targets ==
ALL_TARGETS += $(doc/mans)
CLEANFILES  += $(doc/mans)
