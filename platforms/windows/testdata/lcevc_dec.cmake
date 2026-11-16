# Generated and pinned by platforms/windows/pin_packages.py.
ExternalProject_Add(lcevc_dec
    GIT_REPOSITORY https://github.com/v-novaltd/LCEVCdec.git
    SOURCE_DIR ${SOURCE_LOCATION}
    GIT_CLONE_FLAGS "--filter=tree:0"
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ${EXEC} CONF=1 cmake -S<SOURCE_DIR> -B<BINARY_DIR>
        -G Ninja
        -DCMAKE_BUILD_TYPE=Release
        -DCMAKE_TOOLCHAIN_FILE=${TOOLCHAIN_FILE}
        -DCMAKE_INSTALL_PREFIX=${MINGW_INSTALL_PREFIX}
        -DCMAKE_INSTALL_LIBDIR=lib
        -DCMAKE_POSITION_INDEPENDENT_CODE=ON
        -DBUILD_SHARED_LIBS=OFF
        -DVN_SDK_EXECUTABLES=OFF
        -DVN_SDK_UNIT_TESTS=OFF
        -DVN_SDK_SAMPLE_SOURCE=OFF
        -DVN_SDK_JSON_CONFIG=OFF
        -DVN_SDK_DOCS=OFF
        -DVN_SDK_BUILD_DETAILS=OFF
        -DVN_SDK_TRACING=OFF
        -DVN_SDK_METRICS=OFF
    BUILD_COMMAND ${EXEC} cmake --build <BINARY_DIR>
    INSTALL_COMMAND ${EXEC} cmake --install <BINARY_DIR>
        COMMAND python3 ${CMAKE_CURRENT_LIST_DIR}/fix_lcevc_pkgconfig.py
            ${MINGW_INSTALL_PREFIX}/lib/pkgconfig/lcevc_dec.pc --runtime c++
        COMMAND python3 ${CMAKE_CURRENT_LIST_DIR}/stage_decoder_notices.py
            <SOURCE_DIR> ${MINGW_INSTALL_PREFIX} lcevc_dec
    LOG_DOWNLOAD 1 LOG_UPDATE 1 LOG_CONFIGURE 1 LOG_BUILD 1 LOG_INSTALL 1
)
force_rebuild_git(lcevc_dec)
cleanup(lcevc_dec install)
