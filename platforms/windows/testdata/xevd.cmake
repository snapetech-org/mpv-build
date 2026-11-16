# Generated and pinned by platforms/windows/pin_packages.py.
# The package has no upstream winbuild recipe at the pinned meta-build commit.
if(TARGET_CPU STREQUAL "aarch64")
    set(xevd_arm TRUE)
else()
    set(xevd_arm FALSE)
endif()

ExternalProject_Add(xevd
    GIT_REPOSITORY https://github.com/mpeg5/xevd.git
    SOURCE_DIR ${SOURCE_LOCATION}
    GIT_CLONE_FLAGS "--filter=tree:0"
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ${EXEC} CONF=1 cmake -S<SOURCE_DIR> -B<BINARY_DIR>
        -G Ninja
        -DCMAKE_BUILD_TYPE=Release
        -DCMAKE_TOOLCHAIN_FILE=${TOOLCHAIN_FILE}
        -DCMAKE_INSTALL_PREFIX=${MINGW_INSTALL_PREFIX}
        -DCMAKE_INSTALL_LIBDIR=lib
        -DCMAKE_FIND_ROOT_PATH=${MINGW_INSTALL_PREFIX}
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5
        -DCMAKE_POSITION_INDEPENDENT_CODE=ON
        -DARM=${xevd_arm}
        -DSET_PROF=MAIN
    BUILD_COMMAND ${EXEC} cmake --build <BINARY_DIR> --target xevd
    INSTALL_COMMAND ${EXEC} cmake --install <BINARY_DIR> --component Development
    LOG_DOWNLOAD 1 LOG_UPDATE 1 LOG_CONFIGURE 1 LOG_BUILD 1 LOG_INSTALL 1
)

force_rebuild_git(xevd)
cleanup(xevd install)
