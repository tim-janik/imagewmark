# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

doc/mans :=

# == pandoc ==
doc/markdown-flavour   = markdown-hard_line_breaks+compact_definition_lists+pandoc_title_block+autolink_bare_uris+emoji+lists_without_preceding_blankline

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
