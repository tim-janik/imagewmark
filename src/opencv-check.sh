#!/bin/bash

pkg-config --exists opencv4 && echo "-DHAVE_OPENCV" $(pkg-config --cflags --libs opencv4)
