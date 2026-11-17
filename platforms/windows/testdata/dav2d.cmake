# Generated and pinned by platforms/windows/pin_packages.py.
ExternalProject_Add(dav2d
    GIT_REPOSITORY https://code.videolan.org/videolan/dav2d.git
    SOURCE_DIR ${SOURCE_LOCATION}
    GIT_CLONE_FLAGS "--filter=tree:0"
    GIT_SUBMODULES ""
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ${EXEC} CONF=1 meson setup <BINARY_DIR> <SOURCE_DIR>
        --prefix=${MINGW_INSTALL_PREFIX}
        --libdir=lib
        --cross-file=${MESON_CROSS}
        --default-library=static
        -Denable_tools=false -Denable_tests=false -Denable_asm=false
    BUILD_COMMAND ${EXEC} ninja -C <BINARY_DIR>
    INSTALL_COMMAND ${EXEC} ninja -C <BINARY_DIR> install
        COMMAND python3 ${CMAKE_CURRENT_LIST_DIR}/stage_decoder_notices.py
            <SOURCE_DIR> ${MINGW_INSTALL_PREFIX} dav2d
    LOG_DOWNLOAD 1 LOG_UPDATE 1 LOG_CONFIGURE 1 LOG_BUILD 1 LOG_INSTALL 1
)
force_rebuild_git(dav2d)
force_meson_configure(dav2d)
cleanup(dav2d install)
