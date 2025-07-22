# == Distribution preparation ==
FROM gcc:latest
ENV DEBIAN_FRONTEND=noninteractive

# Use BASH(1) as shell, affects the RUN commands below
RUN ln -sf bash /bin/sh && ls -al /bin/sh

# Add dependencies
RUN apt-get update && apt-get -y upgrade
RUN apt-get install -y build-essential \
	python3-numpy \
	python3-scipy \
	python3-matplotlib \
	python3-imageio \
	python3-opencv \
	python3-skimage \
	libgcrypt20-dev \
	libopenimageio-dev \
	libopencv-dev \
	pandoc

# Setup clean source dir
ADD . /imagewmark
WORKDIR /imagewmark
RUN git clean -f

# Build and install
RUN make all
#RUN make -C install

# Volume for file IO
VOLUME ["/data"]
WORKDIR /data

# Exe for `docker run`
ENTRYPOINT ["/imagewmark/imagewmark"]

# docker build -f Dockerfile -t imagewmark-0 .
# docker run -ti --rm -v $PWD:/data imagewmark-0    gen-key mysecret.key
# docker run -ti --rm -v $PWD:/data imagewmark-0    add --key mysecret.key localimage.png watermarkedimage.png 0123456789abcdef0123456789abcdef
# docker run -ti --rm -v $PWD:/data imagewmark-0    get --key mysecret.key watermarkedimage.png
