cmake_minimum_required(VERSION 2.6)

include(RezBuild)

file(GLOB_RECURSE py_files "python/*.py")
rez_install_python(
    py
    FILES ${py_files}
    DESTINATION .
)


file(GLOB_RECURSE bootstrap_files "bootstrap/*")
rez_install_files(
    ${bootstrap_files}
    DESTINATION .
)


file(GLOB_RECURSE resources_files "resources/*.mel")
rez_install_files(
    ${resources_files}
    DESTINATION .
)
