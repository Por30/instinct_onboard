FROM ros:humble-ros-base-jammy

SHELL ["/bin/bash", "-c"]

RUN sed -i -e 's/^Types:.*/Types: deb/' -e 's#http://ports.ubuntu.com#https://ports.ubuntu.com#g' \
        -e 's#https\{0,1\}://packages.ros.org/ros2/ubuntu#https://mirrors.tuna.tsinghua.edu.cn/ros2/ubuntu#g' \
        /etc/apt/sources.list /etc/apt/sources.list.d/ros2.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       cmake python3-dev python3-venv python3-transforms3d \
       libusb-1.0-0 libudev1 \
       ros-humble-rmw-cyclonedds-cpp ros-humble-rosidl-generator-dds-idl \
       ros-humble-tf-transformations \
    && rm -rf /var/lib/apt/lists/*

RUN /usr/bin/python3 -m venv --system-site-packages /opt/carrybox-venv \
    && /opt/carrybox-venv/bin/python -m pip install --no-cache-dir \
       'numpy==1.26.4' 'onnxruntime==1.20.1' 'pyrealsense2==2.59.2.11152' \
       'opencv-python-headless==4.11.0.86' 'pybind11==2.13.6' \
       numpy-quaternion PyYAML prettytable

ADD unitree_ros2.tar.gz /tmp/unitree_ros2
ADD ros2_numpy.tar.gz /tmp/ros2_numpy
ADD g1_crc.tar.gz /tmp/g1_crc
COPY sources.txt /opt/carrybox-source-revisions.txt

RUN source /opt/ros/humble/setup.bash \
    && mkdir -p /opt/carrybox_ws \
    && cd /opt/carrybox_ws \
    && CMAKE_BUILD_PARALLEL_LEVEL=2 MAKEFLAGS=-j2 colcon build --executor sequential \
       --base-paths /tmp/unitree_ros2/*/cyclonedds_ws/src/unitree /tmp/ros2_numpy/* \
       --packages-select unitree_hg unitree_go ros2_numpy \
       --cmake-args -DBUILD_TESTING=OFF \
    && crc_dir=$(/opt/carrybox-venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["platlib"])') \
    && c++ -O2 -Wall -shared -std=c++14 -fPIC \
       $(/opt/carrybox-venv/bin/python -m pybind11 --includes) \
       /tmp/g1_crc/*/crc_pybind.cpp -o "$crc_dir/crc_module.so" \
    && rm -rf build log /tmp/unitree_ros2 /tmp/ros2_numpy /tmp/g1_crc

ENV PATH="/opt/carrybox-venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
COPY entrypoint.sh /usr/local/bin/carrybox-entrypoint
ENTRYPOINT ["/usr/local/bin/carrybox-entrypoint"]
WORKDIR /work/onboard

# The Jammy transforms3d package uses NumPy aliases removed in 1.24.
RUN python -m pip install --no-cache-dir 'transforms3d==0.4.2'
