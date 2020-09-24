import os
import json

from qpc_base import BaseProjectGenerator, Platform, create_directory
from qpc_project import ConfigType, Language, ProjectContainer, ProjectPass, Configuration
from qpc_logging import warning, error, verbose, print_color, Color
from ..shared import cmd_line_gen
from typing import List


class CompileCommandsGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("compile_commands.json")
        self._add_platforms(Platform.WINDOWS, Platform.LINUX, Platform.MACOS)
        
        self.cmd_gen = cmd_line_gen.CommandLineGen()
        self.commands_list = {}
        self.all_files = {}
    
    def post_args_init(self):
        pass

    def does_project_exist(self, project_out_dir: str) -> bool:
        return False
    
    def projects_finished(self):
        if not self.commands_list:
            return
        print("------------------------------------------------------------------------")
        create_directory("compile_commands")
        for label, commands_list in self.commands_list.items():
            print_color(Color.CYAN, "Writing: " + f"compile_commands/{label}.json")
            compile_commands = json.dumps(commands_list, indent=4)
            with open(f"compile_commands/{label}.json", "w") as file_io:
                file_io.write(compile_commands)
    
    def create_project(self, project: ProjectContainer) -> None:
        project_passes: List[ProjectPass] = self._get_passes(project)
        if not project_passes:
            return

        print_color(Color.CYAN, "Adding to Compile Commands: " + project.file_name)
        
        for proj_pass in project_passes:
            self.cmd_gen.set_mode(proj_pass.cfg.general.compiler)
            label = f"{proj_pass.cfg_name.lower()}_{proj_pass.platform.name.lower()}_{proj_pass.arch.name.lower()}"
            if label not in self.all_files:
                self.all_files[label] = set()
            if label not in self.commands_list:
                self.commands_list[label] = []
                
            for file in proj_pass.source_files:
                if file not in self.all_files[label]:
                    self.all_files[label].add(file)
                    self.commands_list[label].append(self.handle_file(file, proj_pass))
            
    def handle_file(self, file: str, project: ProjectPass) -> dict:
        file_dict = {
            "directory": os.getcwd().replace("\\", "/"),
            "command": cmd_line_gen.get_compiler(project.cfg.general.compiler, project.cfg.general.language) + " ",
            "file": file
        }
        
        file_dict["command"] += " ".join(self.cmd_gen.convert_defines(project.cfg.compile.defines))
        file_dict["command"] += " " + " ".join(self.cmd_gen.convert_includes(project.cfg.compile.inc_dirs))
        
        file_dict["command"] += " " + " ".join(project.cfg.compile.options)
        if f"{self.cmd_gen.switch}c" not in project.cfg.compile.options:
            file_dict["command"] += f" {self.cmd_gen.switch}c"
            
        file_dict["command"] += " " + file
        
        return file_dict
        
        


