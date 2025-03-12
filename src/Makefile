# Licensed under the GNU GPL-3.0+: https://www.gnu.org/licenses/gpl-3.0.html
CXXFLAGS = -O2 -Wall -g -std=c++17

all: peaks2grid cornersync

peaks2grid: peaks2grid.cc minsearch.hh
	$(CXX) $(CXXFLAGS) -o peaks2grid peaks2grid.cc $(shell ./opencv-check.sh)

cornersync: cornersync.cc
	$(CXX) $(CXXFLAGS) -o cornersync cornersync.cc $(shell ./opencv-check.sh)

check:

clean:
	rm -f peaks2grid convcode cornersync
