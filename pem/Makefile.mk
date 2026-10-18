# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
# Self-contained Makefile for PEM — works from within this directory.

setup:
SHELL		:= /bin/bash -o pipefail
Q		:= $(if $(findstring 1, $(V)),, @)
QGEN		 = @echo '  GEN     ' $@

.PHONY: setup check clean

# Butteraugli shared library (3-norm and 2-norm in wrapper.cc, upstream source downloaded at a fixed commit)
BUTTERAUGLI_SRC  := butteraugli-build/butteraugli/butteraugli.cc
BUTTERAUGLI_WRAP := butteraugli-build/wrapper.cc
BUTTERAUGLI_INC  := -I butteraugli-build
BUTTERAUGLI_URL  := https://raw.githubusercontent.com/google/butteraugli/71b18b636b9c7d1ae0c1d3730b85b3c127eb4511/butteraugli
butteraugli.cc.SHA256 := a5f0ae1696955e33a2761395ef6df4ffa320812626324161bb8215d2d9b47c58
butteraugli.h.SHA256  := 64d0c2838a307ef603cfe376976df4f2c246898c021dde5468cf63bcd1737231

butteraugli-build/butteraugli/%:
	$(QGEN)
	$(Q) mkdir -p $(@D)
	$(Q) curl -fsSL -o $@.tmp $(BUTTERAUGLI_URL)/$*
	$(Q) echo "$($*.SHA256)  $@.tmp" | sha256sum --quiet -c -
	$(Q) mv $@.tmp $@

libbutteraugli.so: $(BUTTERAUGLI_SRC) $(BUTTERAUGLI_WRAP) | butteraugli-build/butteraugli/butteraugli.h
	$(QGEN)
	$(Q) g++ -std=c++17 -O2 -fPIC -shared \
		$(BUTTERAUGLI_INC) $^ \
		-o $@

PEM_VENV	:= .venv
PEM_PYTHON	:= $(PEM_VENV)/bin/python3
PEM_STANDALONE_URL := https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-unknown-linux-gnu-install_only.tar.gz

setup: libbutteraugli.so
	$(QGEN)
	# Install standalone Python if not present
	test -f $(PEM_PYTHON) || { \
		echo "Downloading standalone Python 3.12..."; \
		mkdir -p $(PEM_VENV)/bin; \
		curl -fsSL $(PEM_STANDALONE_URL) | tar xz --strip-components=1 -C $(PEM_VENV); \
		ln -sf python3 $(PEM_VENV)/bin/python; \
	}
	$(Q) UV_CACHE_DIR=.uv-cache uv pip install --python $(PEM_PYTHON) \
		--extra-index-url https://download.pytorch.org/whl/cpu \
		torch torchvision 'paddlepaddle>=2.6,<3' 'paddleocr>=2.7,<3' numpy Pillow opencv-python-headless rich tqdm cvvdp scikit-image ssimulacra2
CLEANFILES += libbutteraugli.so

check: setup
	$(QGEN)
	$Q $(PEM_PYTHON) tests/run_tests.py

clean:
	$(QGEN)
	rm -f $(CLEANFILES)
	rm -rf $(CLEANDIRS)

CLEANDIRS += .venv/ .uv-cache/ .cache/ __pycache__/
