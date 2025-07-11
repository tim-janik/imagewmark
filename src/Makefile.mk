# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html

src/watermark       := fedcba98765432100123456789abcdef

# == check ==
define CHECK_RESOLUTION
src/check-$1:
	$(Q) echo '  CHECK   ' $$@
	$(Q) convert tests/example01.svg -resize $1 $$@.png
	$(Q) ./imagewmark add $$@.png $$@.wm.png $(src/watermark)
	$(Q) test $1 -gt 2048 \
	|| { convert $$@.wm.png -resize 1024 $$@.small.png && mv $$@.small.png $$@.wm.png ; }
	$(Q) ./imagewmark get $$@.wm.png --json $$@.json
	$(Q) grep -qE '\b$(src/watermark)\b' $$@.json || \
		{ echo "$$@.png: failed to detect watermark" >&2 ; false ; }
	$(Q) rm $$@.png $$@.wm.png $$@.json
	$(Q) echo '  OK      ' $$@
.PHONY: src/check-$1
src/check: src/check-$1
endef
CHECK_RESOLUTIONS := 1024 2048 3072 4096 # 8192
$(foreach R, $(CHECK_RESOLUTIONS), $(eval $(call CHECK_RESOLUTION,$R)))
.PHONY: src/check
check: src/check

