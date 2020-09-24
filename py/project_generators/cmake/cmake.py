import os

from qpc_args import args
from qpc_base import BaseProjectGenerator, Platform, Arch, is_arch_64bit
from qpc_project import ConfigType, Language, ProjectContainer, ProjectPass, Configuration, ProjectDefinition
from qpc_parser import BaseInfo, BaseInfoPlatform
from qpc_logging import warning, error, verbose, print_color, Color
from ..shared import cmd_line_gen, msvc_tools
from typing import List


class CMakeGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("CMake Generator")
        self._add_platforms(Platform.WINDOWS, Platform.LINUX, Platform.MACOS)
        self._set_generate_master_file(True)
        self._set_macro("CMAKE")

        self.cmd_gen = cmd_line_gen.CommandLineGen()
        self.cmake_dirs = []

    def does_project_exist(self, project_out_dir: str) -> bool:
        # TODO: check if the cmake file exists and contains an add_target line for this project
        # ...except i don't know what the config_type is at this stage, so we can't really do that
        # unless i hash it, but that's dumb, instead,
        # generators should optionally be able to add stuff to a project's hash file
        return False
    
    # what was i thinking with this function again?
    def get_master_file_path(self, master_file_path: str) -> str:
        return master_file_path
    
    def set_platform_and_archs(self, platform: Platform, arch: Arch) -> str:
        string = "if" + ifndef("QPC_PLATFORM", f"\tset(QPC_PLATFORM \"{platform.name}\")")
        string += "\n\nif" + ifndef(
            "QPC_ARCH",
            f"\tset(QPC_ARCH \"{arch.name}\")"
            # + f"\n\tset(CMAKE_GENERATOR_PLATFORM \"{'x86' if arch == Arch.I386 else 'x64'}\")"
        )
        return string
    
    # write a master CMakeLists.txt file
    def create_master_file(self, settings: BaseInfo, master_file_path: str) -> str:
        main_cmakelists = "cmake_minimum_required(VERSION 3.5)\n\n"
        main_cmakelists += f"project({os.path.basename(master_file_path)})\n\n"

        print_color(Color.CYAN, "Creating Master CMakeLists.txt")
        
        # this chooses 64 bit architectures over 32 bit for a default arch
        architecture: Arch = args.archs[0]
        for arch in args.archs:
            if not architecture or is_arch_64bit(arch) and architecture and not is_arch_64bit(architecture):
                architecture = arch
                
        main_cmakelists += self.set_platform_and_archs(settings.info_list[0].platform, architecture)
        main_cmakelists += "\n\n"
        
        subdirs = set()
        for project in settings.projects:
            path = os.path.split(project.path)[0]
            if path not in subdirs:
                main_cmakelists += f"add_subdirectory({path})\n"
                subdirs.add(path)
        
        with open("CMakeLists.txt", "w", encoding="utf8") as cmakelist_io:
            cmakelist_io.write(main_cmakelists)
        
        return ""

    def create_project(self, project: ProjectContainer) -> None:
        project_passes: List[ProjectPass] = self._get_passes(project)
        if not project_passes:
            return

        print_color(Color.CYAN, "CMake Generator Running on " + project.file_name)

        main_cmakelists = ""
        if os.getcwd() not in self.cmake_dirs:
            self.cmake_dirs.append(os.getcwd())
            main_cmakelists += self.gen_declaration(project_passes)
        else:
            if os.path.isfile("CMakeLists.txt"):
                # check for cmake_minimum_required( in file?
                with open("CMakeLists.txt", "r", encoding="utf8") as cmakelist_io:
                    main_cmakelists += cmakelist_io.read()
                
        for i, proj in enumerate(project_passes):
            main_cmakelists += "else" if i != 0 else ""
            # NOTE - can't use custom build types with CMAKE_BUILD_TYPE, really sucks
            main_cmakelists += "if( " + \
                               strequal("CMAKE_BUILD_TYPE", proj.cfg_name) + " AND " + \
                               strequal("QPC_PLATFORM", proj.platform.name) + " AND " + \
                               strequal("QPC_ARCH", proj.arch.name) + " )\n"
            
            main_cmakelists += self.handle_pass(proj)
            
        main_cmakelists += "endif()\n\n"
        
        # issue - could be multiple projects in this same folder
        with open("CMakeLists.txt", "w", encoding="utf8") as cmakelist_io:
            cmakelist_io.write(main_cmakelists)
        
    def gen_declaration(self, project_passes: List[ProjectPass]) -> str:
        # i don't actually know what the minimum here would be
        declaration = "cmake_minimum_required(VERSION 3.5)\n\n"
        
        declaration += self.set_platform_and_archs(project_passes[0].platform, project_passes[0].arch)
        
        declaration += f"\n\n"
                
        return declaration
                
    def handle_pass(self, proj: ProjectPass) -> str:
        cmakelists = ""
        # proj_name = proj.config.general.out_name.upper()
        proj_name = proj.container.file_name.upper()
        
        self.cmd_gen.set_mode(proj.cfg.general.compiler)
        
        if proj.cfg.general.config_type == ConfigType.APPLICATION:
            target = "executable"
        else:
            target = "library"

        cmakelists += "\n" + gen_list_option("set", f"{proj_name}_SRC_FILES", *abspathlist(list(proj.source_files)))
        cmakelists += gen_list_option("set", f"{proj_name}_INC_FILES", *abspathlist(proj.get_headers()))

        if proj.cfg.general.config_type == ConfigType.STATIC_LIB:
            target_type = " STATIC"
        elif proj.cfg.general.config_type == ConfigType.DYNAMIC_LIB:
            target_type = " SHARED"
        else:
            target_type = ""
            
        cmakelists += gen_option(f"\tadd_{target}", f"{proj_name}{target_type}",
                                 f"${{{proj_name}_SRC_FILES}}",
                                 f"${{{proj_name}_INC_FILES}}")

        lang = "CXX" if proj.cfg.general.language == Language.CPP else "C"

        target_props = {
            "PREFIX":                       f"\"{proj.cfg.general.out_name_prefix}\"",
            "OUTPUT_NAME":                  f"\"{proj.cfg.general.out_name}\"",
            f"{lang}_COMPILER":             f"\"{proj.cfg.general.compiler}\"",
            f"{lang}_STANDARD":             proj.cfg.general.standard.name[len(proj.cfg.general.language.name):],
            # f"{lang}_STANDARD_REQUIRED":    "YES"
        }

        if proj.cfg.general.config_type == ConfigType.STATIC_LIB:
            cmake_output_dir = "ARCHIVE_OUTPUT_DIRECTORY"
            # cmake_output_dir = "LIBRARY_OUTPUT_DIRECTORY"
        else:
            cmake_output_dir = "RUNTIME_OUTPUT_DIRECTORY"
        
        output_dir = proj.cfg.general.out_dir
        if proj.cfg.link.output_file:
            output_dir = os.path.split(proj.cfg.link.output_file)[0]

        target_props[cmake_output_dir] = q_abspath(output_dir)

        if proj.cfg.link.import_lib:
            target_props["ARCHIVE_OUTPUT_DIRECTORY"] = q_abspath(os.path.split(proj.cfg.link.import_lib)[0])

        target_props_strs = [f"{k} {v}" for k, v in target_props.items()]
        cmakelists += "\n" + gen_list_option("set_target_properties", f"{proj_name} PROPERTIES", *target_props_strs)
        
        if proj.cfg.compile.inc_dirs:
            inc_dirs = abspathlist(proj.cfg.compile.inc_dirs)
            if proj.cfg.compile.default_inc_dirs and proj.platform == Platform.WINDOWS:
                inc_dirs.extend(abspathlist(msvc_tools.get_inc_dirs("")))
            cmakelists += gen_target_option("include_directories", f"{proj_name} PRIVATE", *inc_dirs)
        
        if proj.cfg.link.lib_dirs:
            lib_dirs = abspathlist(proj.cfg.link.lib_dirs)
            if proj.cfg.link.default_lib_dirs and proj.platform == Platform.WINDOWS:
                lib_dirs.extend(abspathlist(msvc_tools.get_lib_dirs("")))
            cmakelists += gen_target_option("link_directories", f"{proj_name} PRIVATE", *lib_dirs)
        
        if proj.cfg.link.libs:
            libs = []
            for lib in proj.cfg.link.libs:
                if os.path.split(lib)[0]:
                    if not os.path.splitext(lib)[1]:
                        lib += proj.macros["EXT_LIB"]
                    libs.append(q_abspath(lib))
                else:
                    # libs.append(f"\"{lib}\"")
                    libs.append(lib)
                
            cmakelists += gen_target_option("link_libraries", proj_name, *libs)
        
        if proj.cfg.compile.defines:
            cmakelists += gen_add_definitions(f"{proj_name} PRIVATE", proj.cfg.compile.defines)

        if proj.cfg.compile.options:
            cmakelists += gen_target_option("compile_options", f"{proj_name} PRIVATE", *proj.cfg.compile.options)
        
        link_options = []
        if proj.cfg.link.ignore_libs:
            link_options.extend(self.cmd_gen.ignore_libs(proj.cfg.link.ignore_libs))
            
        if proj.cfg.link.options:
            link_options.extend(proj.cfg.link.options)
            
        if link_options:
            cmakelists += gen_target_option("link_options", f"{proj_name} PRIVATE", *link_options)
        
        return cmakelists
    
    
def abspath(path: str) -> str:
    return os.path.abspath(path).replace("\\", "/")
    
    
def q_abspath(path: str) -> str:
    return f"\"{abspath(path)}\""
    
    
def abspathlist(paths: list) -> list:
    return [q_abspath(path) for path in paths]
    
    
def ifndef(var: str, text: str) -> str:
    return f"(NOT DEFINED {var})\n{text}\nendif()"
    
    
def ifdef(var: str, text: str) -> str:
    return f"(DEFINED {var})\n{text}\nendif()"
    
    
def strequal(str1: str, str2: str) -> str:
    return f"({str1} STREQUAL {str2})"
    
    
def gen_add_definitions(proj_name: str, defines: List[str]) -> str:
    return gen_list_option_custom("target_compile_definitions", proj_name, "\n\t\t-D", *defines)
        
        
def gen_list_option_custom(target: str, name: str, join_char: str, *args) -> str:
    return f"\t{target}(\n\t\t{name}{join_char}" + join_char.join(args) + "\n\t)\n\n"
    
    
def gen_target_option(target: str, *args) -> str:
    return f"\ttarget_{target}(\n\t\t" + "\n\t\t".join(args) + "\n\t)\n\n"


def gen_list_option(target: str, *args) -> str:
    return f"\t{target}(\n\t\t" + "\n\t\t".join(args) + "\n\t)\n\n"


def gen_option(target: str, *args) -> str:
    return f"{target}( " + " ".join(args) + " )\n"




