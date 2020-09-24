
project( QuiverProjectCreator )
set( CMAKE_CXX_STANDARD 17 )
set( CMAKE_CXX_STANDARD_REQUIRED ON )
set( CMAKE_CXX_EXTENSIONS OFF )

if ( MINGW )
	set( CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wno-long-long -pedantic" )
	set( CMAKE_EXE_LINKER_FLAGS "-static-libgcc -static-libstdc++ -static" )
endif()

add_executable( qpc src/main.cpp )